# -*- coding: utf8 -*-
# Copyright (c) 2014 by Ecreall under licence AGPL terms 
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import datetime
from persistent.list import PersistentList
from pyramid.threadlocal import get_current_registry
from pyramid.httpexceptions import HTTPFound

from substanced.util import get_oid

from dace.objectofcollaboration.principal.util import (
    has_role,
    grant_roles,
    get_current,
    revoke_roles,
    has_any_roles)
from dace.processinstance.activity import InfiniteCardinality
from dace.util import find_catalog, getSite
from dace.processinstance.core import ActivityExecuted

from ..user_management.behaviors import global_user_processsecurity
from novaideo.content.interface import (
    ISignalableEntity,
    ISReport)
from novaideo import _, nothing
from novaideo.views.filter import (
    find_entities, get_random_users)
from novaideo.adapters.report_adapter import ISignalableObject
from novaideo.utilities.alerts_utility import (
    alert, get_user_data, get_entity_data)
from novaideo.utilities.util import to_localized_time
from novaideo.content.alert import InternalAlertKind
from novaideo.content.processes.content_ballot_management import (
    ballot_result, close_ballot,
    ELECTORS_NB, start_ballot,
    get_ballot_alert_data)
from novaideo.content.processes.content_ballot_management.behaviors import (
    StartBallot)


_marker = object()


def ignore(context, request, root):
    user = get_current()
    context_oid = get_oid(context)
    dace_index = find_catalog('dace')
    dace_container_oid = dace_index['container_oid']
    query = dace_container_oid.eq(context_oid)
    reports = find_entities(
        interfaces=[ISReport],
        metadata_filter={
            'states': ['pending']},
        user=user,
        add_query=query)
    for report in reports:
        report.state = PersistentList(['processed'])
        report.reindex()

    context.init_len_current_reports()
    context.state.remove('reported')
    context.reindex()


def censor(context, request, root, **kw):
    context_oid = get_oid(context)
    dace_index = find_catalog('dace')
    dace_container_oid = dace_index['container_oid']
    query = dace_container_oid.eq(context_oid)
    reports = find_entities(
        interfaces=[ISReport],
        metadata_filter={
            'states': ['pending']},
        add_query=query)
    for report in reports:
        report.state = PersistentList(['processed'])
        report.reindex()

    context.init_len_current_reports()
    adapter = get_current_registry().queryAdapter(
        context, ISignalableObject)
    if adapter is not None:
        context.state.remove('reported')
        adapter.censor(request, ballot_url=kw.get('ballot_url', ''))


def report_roles_validation(process, context):
    return has_role(role=('Member',))


def report_processsecurity_validation(process, context):
    report_ballots = [b for b in context.ballots
                      if b.group_id == 'vote_moderation'
                      and context in b.subjects
                      and b.is_finished
                      and b.report.get_electeds() is not None
                      and b.decision_is_valide]
    can_report = getattr(get_current(), 'can_report', lambda: True)
    return can_report() and not report_ballots and global_user_processsecurity()


def report_state_validation(process, context):
    return "published" in context.state


class Report(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'plus-action'
    style_interaction = 'ajax-action'
    style_picto = 'md md-sms-failed'
    style_order = 100
    isSequential = False
    submission_title = _('Continue')
    context = ISignalableEntity
    roles_validation = report_roles_validation
    processsecurity_validation = report_processsecurity_validation
    state_validation = report_state_validation

    def start(self, context, request, appstruct, **kw):
        user = get_current()
        report = appstruct['_object_data']
        context.addtoproperty('reports', report)
        report.state.append('pending')
        context.state.append('reported')
        grant_roles(user=user, roles=(('Owner', report), ))
        report.setproperty('author', user)
        report.reindex()
        context.reindex()
        if hasattr(user, 'add_report'):
            user.add_report(context)

        root = getSite()
        # get random moderators
        ballots = [b for b in getattr(context, 'ballot_processes', [])
                   if b.id == 'contentreportdecision']
        if not ballots:
            moderators = get_random_users(ELECTORS_NB, [context.author])
            if not moderators:
                ignore(context, request, root)
            else:
                author = context.author

                def before_start(b_proc):
                    b_proc.content = context

                start_ballot(
                    context, author, request, root,
                    moderators, 'contentreportdecision',
                    before_start=before_start,
                    initiator=user,
                    subjects=[context])
                alert_data = get_ballot_alert_data(
                    context, request, root, moderators)
                alert_data.update(get_user_data(author, 'recipient', request))
                mail_template = root.get_mail_template(
                    'alert_report', author.user_locale)
                if mail_template:
                    subject = mail_template['subject'].format(
                        **alert_data)
                    message = mail_template['template'].format(
                        **alert_data)
                    alert('email', [root.get_site_sender()], [author.email],
                          subject=subject, body=message)


        return {}

    def redirect(self, context, request, **kw):
        return nothing


def reportmax_processsecurity_validation(process, context):
    report_ballots = [b for b in context.ballots
                      if b.group_id == 'vote_moderation'
                      and context in b.subjects
                      and b.is_finished
                      and b.report.get_electeds() is not None
                      and b.decision_is_valide]
    can_report = getattr(get_current(), 'can_report', lambda: True)
    return not can_report() and not report_ballots and global_user_processsecurity()


class ReportMax(Report):
    style_picto = 'md md-sms-failed disabled'
    processsecurity_validation = reportmax_processsecurity_validation
    
    def start(self, context, request, appstruct, **kw):
        return {}


def restor_roles_validation(process, context):
    return has_role(role=('Moderator',))


def decision_processsecurity_validation(process, context):
    return global_user_processsecurity()


def restor_state_validation(process, context):
    return "censored" in context.state


class Restor(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'plus-action'
    style_interaction = 'ajax-action'
    style_picto = 'glyphicon glyphicon-refresh'
    style_order = 102
    isSequential = False
    submission_title = _('Continue')
    context = ISignalableEntity
    roles_validation = restor_roles_validation
    processsecurity_validation = decision_processsecurity_validation
    state_validation = restor_state_validation

    def start(self, context, request, appstruct, **kw):
        adapter = get_current_registry().queryAdapter(
            context, ISignalableObject)
        if adapter is not None:
            adapter.restor(request)

        context.reindex()
        return {}

    def redirect(self, context, request, **kw):
        return nothing


def seerep_roles_validation(process, context):
    return has_any_roles(roles=('Moderator', ('LocalModerator', context)))


def seerep_processsecurity_validation(process, context):
    return getattr(context, 'len_reports', 0) and global_user_processsecurity()


class SeeReports(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'communication-action'
    style_picto = 'md md-sms-failed'
    style_interaction = 'ajax-action'
    style_interaction_type = 'sidebar'
    style_order = 103
    context = ISignalableEntity
    roles_validation = seerep_roles_validation
    processsecurity_validation = seerep_processsecurity_validation

    def get_nb(self, context, request):
        return getattr(context, 'len_current_reports', 0)

    def get_title(self, context, request, nb_only=False):
        len_reports = self.get_nb(context, request)
        if nb_only:
            return str(len_reports)

        return _("${title} (${number})",
                 mapping={'number': len_reports,
                          'title': request.localizer.translate(self.title)})

    def start(self, context, request, appstruct, **kw):
        return {}

    def redirect(self, context, request, **kw):
        return nothing


# Idea moderation

def decision_state_validation(process, context):
    return 'reported' in context.state


class ModerationVote(StartBallot):
    context = ISignalableEntity
    state_validation = decision_state_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        moderators = self.process.execution_context.get_involved_collection(
            'electors')
        alert(
            'internal', [root], moderators,
            internal_kind=InternalAlertKind.moderation_alert,
            subjects=[context], alert_kind='moderate_report')
        subject_data = get_entity_data(context, 'subject', request)
        subject_data.update(get_user_data(context, 'subject', request))
        duration = getattr(root, 'duration_moderation_vote', 7)
        date_end = datetime.datetime.now() + \
            datetime.timedelta(days=duration)
        date_end_vote = to_localized_time(
            date_end, request, translate=True)
        subject_data['url_moderation_rules'] = request.resource_url(
            root.moderation_rules, '@@index')
        for moderator in [a for a in moderators if getattr(a, 'email', '')]:
            mail_template = root.get_mail_template(
                'moderate_report', moderator.user_locale)
            subject = mail_template['subject'].format(
                novaideo_title=root.title)
            email_data = get_user_data(moderator, 'recipient', request)
            email_data.update(subject_data)
            message = mail_template['template'].format(
                novaideo_title=root.title,
                subject_email=getattr(context, 'email', ''),
                date_end_vote=date_end_vote,
                duration=duration,
                **email_data)
            alert('email', [root.get_site_sender()], [moderator.email],
                  subject=subject, body=message)

        request.registry.notify(ActivityExecuted(
            self, [context], get_current()))
        return {}

    def after_execution(self, context, request, **kw):
        content = self.process.execution_context.involved_entity(
            'content')
        close_ballot(self, content, request)
        # content not removed
        if content and content.__parent__:
            root = getSite()
            moderators = self.process.execution_context.get_involved_collection(
                'electors')
            for moderator in moderators:
                revoke_roles(
                    user=moderator,
                    roles=(('LocalModerator', content),))

            ballots = getattr(self.sub_process, 'ballots', [])
            ballot = None
            for ballot_ in ballots:
                ballot_.finish_ballot()
                ballot = ballot_

            ballot_oid = get_oid(ballot, '')
            ballot_url = request.resource_url(
                root, '@@seeballot', query={'id': ballot_oid}) \
                if ballot_oid else None
            accepted = ballot_result(self, _marker)
            if accepted:
                ignore(content, request, root)
                alert(
                    'internal', [request.root], moderators,
                    internal_kind=InternalAlertKind.moderation_alert,
                    subjects=[content], alert_kind='object_report_ignored',
                    ballot=ballot_url if accepted is not _marker else None)
            else:
                censor(content, request, root, ballot_url=ballot_url)
                alert(
                    'internal', [request.root], moderators,
                    internal_kind=InternalAlertKind.moderation_alert,
                    subjects=[content], alert_kind='object_censor',
                    ballot=ballot_url)

        super(ModerationVote, self).after_execution(
            content, request, **kw)

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, "@@index"))

#TODO behaviors
