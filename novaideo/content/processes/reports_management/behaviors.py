# -*- coding: utf8 -*-
# Copyright (c) 2014 by Ecreall under licence AGPL terms 
# avalaible on http://www.gnu.org/licenses/agpl.html 

# licence: AGPL
# author: Amen Souissi

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
from novaideo.content.alert import InternalAlertKind
from novaideo.content.processes.moderation_management import (
    moderation_result, close_ballot,
    MODERATORS_NB, start_moderation)
from novaideo.content.processes.moderation_management.behaviors import (
    ModerationVote as ModerationVoteBase)


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


def censor(context, request, root):
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
        adapter.censor(request)


def select_roles_validation(process, context):
    return has_role(role=('Member',))


def select_processsecurity_validation(process, context):
    return global_user_processsecurity()


def select_state_validation(process, context):
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
    roles_validation = select_roles_validation
    processsecurity_validation = select_processsecurity_validation
    state_validation = select_state_validation

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
        root = getSite()
        # get random moderators
        if not context.moderation_proc:
            moderators = get_random_users(MODERATORS_NB)
            if not moderators:
                ignore(context, request, root)
            else:
                author = context.author
                start_moderation(
                    context, author, request, root,
                    'content_submit', moderators,
                    'contentreportdecision')

        return {}

    def redirect(self, context, request, **kw):
        return nothing


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

    def get_title(self, context, request):
        len_reports = self.get_nb(context, request)
        return _("${title} (${nember})",
                 mapping={'nember': len_reports,
                          'title': request.localizer.translate(self.title)})

    def start(self, context, request, appstruct, **kw):
        return {}

    def redirect(self, context, request, **kw):
        return nothing


# Idea moderation

def decision_state_validation(process, context):
    return 'reported' in context.state


class ModerationVote(ModerationVoteBase):
    context = ISignalableEntity
    state_validation = decision_state_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        moderators = context.moderators
        alert(
            'internal', [root], moderators,
            internal_kind=InternalAlertKind.moderation_alert,
            subjects=[context], alert_kind='moderate_content')
        mail_template = root.get_mail_template('moderate_content')
        subject = mail_template['subject'].format(
            novaideo_title=root.title)
        subject_data = get_entity_data(context, 'subject', request)
        subject_data.update(get_user_data(context, 'subject', request))
        for moderator in [a for a in moderators if getattr(a, 'email', '')]:
            email_data = get_user_data(moderator, 'recipient', request)
            email_data.update(subject_data)
            message = mail_template['template'].format(
                novaideo_title=root.title,
                subject_email=getattr(context, 'email', ''),
                duration=getattr(root, 'duration_moderation_vote', 7),
                **email_data)
            alert('email', [root.get_site_sender()], [moderator.email],
                  subject=subject, body=message)

        request.registry.notify(ActivityExecuted(
            self, [context], get_current()))
        return {}

    def after_execution(self, context, request, **kw):
        content = self.process.execution_context.created_entity(
            'content')
        close_ballot(self, content, request)
        # proposal not removed
        if content and content.__parent__:
            for moderator in content.moderators:
                revoke_roles(
                    user=moderator,
                    roles=(('LocalModerator', content),))

            accepted = moderation_result(self.process)
            root = getSite()
            if accepted:
                ignore(content, request, root)
            else:
                censor(content, request, root)

        super(ModerationVote, self).after_execution(
            content, request, **kw)

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, "@@index"))

#TODO behaviors
