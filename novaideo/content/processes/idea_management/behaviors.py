# -*- coding: utf8 -*-
# Copyright (c) 2014 by Ecreall under licence AGPL terms
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

"""
This module represent all of behaviors used in the
Idea management process definition.
"""
import datetime
import pytz
from persistent.list import PersistentList
from persistent.dict import PersistentDict
from pyramid.httpexceptions import HTTPFound
from pyramid.threadlocal import get_current_request

from substanced.util import get_oid

from dace.util import (
    getSite,
    getBusinessAction,
    copy)
from dace.objectofcollaboration.principal.util import (
    has_role,
    has_any_roles,
    grant_roles,
    get_current,
    revoke_roles)
from dace.processinstance.activity import InfiniteCardinality, ActionType
from dace.processinstance.core import ActivityExecuted

import html_diff_wrapper

from novaideo.content.interface import (
    INovaIdeoApplication, Iidea, IIdeaSource)
from ..user_management.behaviors import (
    global_user_processsecurity,
    access_user_processsecurity)
from novaideo import _, nothing, log
from novaideo.content.idea import Idea
from ..comment_management import VALIDATOR_BY_CONTEXT
from novaideo.core import Evaluations, access_action, serialize_roles
from novaideo.utilities.util import(
    connect, disconnect, to_localized_time)
from novaideo.event import (
    ObjectPublished, CorrelableRemoved)
from novaideo.utilities.alerts_utility import (
    alert, get_user_data, get_entity_data, alert_comment_nia)
from novaideo.content.alert import InternalAlertKind
from novaideo.views.filter import (
    get_users_by_preferences, get_random_users)
from novaideo.content.proposal import Proposal
from novaideo.content.working_group import WorkingGroup
from novaideo.content.correlation import CorrelationType
from novaideo.content.processes.proposal_management import (
    init_proposal_ballots, add_attached_files)
from novaideo.content.comment import Comment
from novaideo.content.question import Answer
from novaideo.content.processes.content_ballot_management import (
    ballot_result, close_ballot,
    ELECTORS_NB, start_ballot, remove_ballot_processes, get_ballot_alert_data)
from novaideo.content.processes.content_ballot_management.behaviors import (
    StartBallot)


_marker = object()


def publish_idea_moderation(context, request, root, **kw):
    if root.support_ideas:
        context.state = PersistentList(['submitted_support', 'published'])
    else:
        context.state = PersistentList(['published', 'submitted_support'])

    context.init_published_at()
    if context.originalentity:
        # Add Nia comment
        alert_comment_nia(
            context.originalentity, request, root,
            internal_kind=InternalAlertKind.content_alert,
            subject_type='idea',
            alert_kind='duplicated',
            duplication=context
            )
    if getattr(context, '_tree', None):
        tree = getattr(context, '_tree')
        root.merge_tree(tree)

    context.reindex()
    user = context.author
    alert('internal', [root], [user],
          internal_kind=InternalAlertKind.moderation_alert,
          subjects=[context], alert_kind='moderation',
          ballot=kw.get('ballot_url', ''))
    if getattr(user, 'email', ''):
        mail_template = root.get_mail_template(
            'publish_idea_decision', user.user_locale)
        subject = mail_template['subject'].format(
            subject_title=context.title)
        email_data = get_user_data(user, 'recipient', request)
        email_data.update(get_entity_data(context, 'subject', request))
        message = mail_template['template'].format(
            novaideo_title=root.title,
            **email_data
        )
        alert('email', [root.get_site_sender()], [user.email],
              subject=subject, body=message)

    request.registry.notify(ObjectPublished(object=context))


def archive_idea(context, request, root, appstruct, **kw):
    explanation = appstruct['explanation']
    context.state = PersistentList(['archived'])
    context.remove_tokens(True)
    context.reindex()
    user = context.author
    alert('internal', [root], [user],
          internal_kind=InternalAlertKind.moderation_alert,
          subjects=[context], alert_kind='moderation',
          ballot=kw.get('ballot_url', ''))

    if getattr(user, 'email', ''):
        mail_template = root.get_mail_template(
            'archive_idea_decision', user.user_locale)
        subject = mail_template['subject'].format(
            subject_title=context.title)
        email_data = get_user_data(user, 'recipient', request)
        email_data.update(get_entity_data(context, 'subject', request))
        message = mail_template['template'].format(
            explanation=explanation,
            novaideo_title=root.title,
            **email_data
        )
        alert('email', [root.get_site_sender()], [user.email],
              subject=subject, body=message)


def createidea_roles_validation(process, context):
    return has_role(role=('Member',))


def createidea_processsecurity_validation(process, context):
    return global_user_processsecurity()


class CreateIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'lateral-action'
    style_interaction = 'ajax-action'
    style_picto = 'icon novaideo-icon icon-idea'
    style_order = 0
    title = _('Create an idea')
    unavailable_link = 'docanonymous'
    submission_title = _('Save')
    context = INovaIdeoApplication
    roles_validation = createidea_roles_validation
    processsecurity_validation = createidea_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        user = get_current(request)
        mask = user.get_mask(root) if hasattr(user, 'get_mask') else user
        author = mask if appstruct.get('anonymous', False) and mask else user
        idea = appstruct['_object_data']
        root.addtoproperty('ideas', idea)
        idea.state.append('to work')
        grant_roles(user=author, roles=(('Owner', idea), ))
        idea.setproperty('author', author)
        idea.subscribe_to_channel(user)
        if isinstance(context, (Comment, Answer)):
            content = context.subject
            correlations = connect(
                content,
                [idea],
                {'comment': context.comment,
                 'type': getattr(context, 'intention',
                                 'Transformation from another content')},
                author,
                ['transformation'],
                CorrelationType.solid)
            for correlation in correlations:
                correlation.setproperty('context', context)

            context_type = context.__class__.__name__.lower()
            # Add Nia comment
            alert_comment_nia(
                idea, request, root,
                internal_kind=InternalAlertKind.content_alert,
                subject_type='idea',
                alert_kind='transformation_'+context_type,
                content=context
                )

        idea.format(request)
        idea.reindex()
        request.registry.notify(ActivityExecuted(self, [idea], author))
        return {'newcontext': idea}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(kw['newcontext'], "@@index"))


class CrateAndPublish(InfiniteCardinality):
    style_picto = 'icon novaideo-icon icon-idea'
    style_order = 1
    title = _('Create and publish')
    # submission_title = _('Save and publish')
    context = IIdeaSource
    roles_validation = createidea_roles_validation
    processsecurity_validation = createidea_processsecurity_validation

    @property
    def submission_title(self):
        request = get_current_request()
        if getattr(request, 'moderate_ideas', False):
            return _('Save and submit')

        return _('Save and publish')

    def start(self, context, request, appstruct, **kw):
        create_actions = self.process.get_actions('creat')
        create_action = create_actions[0] if create_actions else None
        idea = None
        root = getSite()
        if create_action:
            result = create_action.start(context, request, appstruct, **kw)
            idea = result.get('newcontext', None)
            if idea:
                user = get_current(request)
                mask = user.get_mask(root) if hasattr(user, 'get_mask') else user
                author = mask if appstruct.get('anonymous', False) and mask else user
                idea.subscribe_to_channel(user)
                if request.moderate_ideas:
                    submit_actions = self.process.get_actions('submit')
                    submit_action = submit_actions[0] if submit_actions else None
                    if submit_action:
                        submit_action.start(idea, request, {'user': author})
                else:
                    publish_actions = self.process.get_actions('publish')
                    publish_action = publish_actions[0] if publish_actions else None
                    if publish_action:
                        publish_action.start(idea, request, {'user': author})

                return {'newcontext': idea, 'state': True}

        return {'newcontext': root, 'state': False}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(kw['newcontext'], "@@index"))


class CrateAndPublishAsProposal(CrateAndPublish):
    style_picto = 'icon novaideo-icon icon-idea'
    style_order = 2
    title = _('Create a Working Group')
    submission_title = _('Create a Working Group')

    def start(self, context, request, appstruct, **kw):
        result = super(CrateAndPublishAsProposal, self).start(
            context, request, appstruct, **kw)
        root = getSite()
        state = result.get('state', False)
        if state:
            idea = result.get('newcontext', None)
            if idea:
                user = get_current(request)
                mask = user.get_mask(root) if hasattr(user, 'get_mask') else user
                author = mask if appstruct.get('anonymous', False) and mask else user
                idea.subscribe_to_channel(user)
                related_ideas = [idea]
                localizer = request.localizer
                title = idea.title + \
                    localizer.translate(_(" (the proposal)"))
                template = getattr(root, 'proposal_template', None)
                text = '<p>{idea_text}</p>'
                if template:
                    try:
                        text = template.fp.readall().decode()
                    except Exception as error:
                        log.warning(error)

                proposal = Proposal(
                    title=title,
                    description=idea.text[:600],
                    text=text.format(
                        idea_text=idea.text.replace('\n', '<br/>')),
                    keywords=list(idea.keywords)
                    )
                proposal.text = html_diff_wrapper.normalize_text(proposal.text)
                root.addtoproperty('proposals', proposal)
                proposal.state.append('draft')
                grant_roles(user=author, roles=(('Owner', proposal), ))
                grant_roles(user=author, roles=(('Participant', proposal), ))
                proposal.setproperty('author', author)
                challenge = idea.challenge
                if challenge:
                    proposal.setproperty('challenge', challenge)

                wg = WorkingGroup()
                root.addtoproperty('working_groups', wg)
                wg.init_workspace()
                wg.setproperty('proposal', proposal)
                wg.addtoproperty('members', author)
                wg.state.append('deactivated')
                if related_ideas:
                    connect(proposal,
                            related_ideas,
                            {'comment': _('Add related ideas'),
                             'type': _('Creation')},
                            author,
                            ['related_proposals', 'related_ideas'],
                            CorrelationType.solid)
                try:
                    files = {
                        'add_files': {
                            'attached_files': [{'_object_data': f.copy()} for
                                               f in idea.attached_files]
                        }
                    }
                    add_attached_files(files, proposal)
                except Exception:
                    pass

                proposal.subscribe_to_channel(user)
                proposal.reindex()
                init_proposal_ballots(proposal)
                wg.reindex()
                request.registry.notify(
                    ActivityExecuted(self, [idea, proposal, wg], author))
                return {'newcontext': proposal}

        return {'newcontext': root}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(kw['newcontext'], "@@index"))


def duplicate_processsecurity_validation(process, context):
    return ((has_role(role=('Owner', context)) and \
            'archived' not in context.state or \
            'version' in context.state) or \
            'published' in context.state) and \
        global_user_processsecurity()


class DuplicateIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'global-action'
    style_interaction = 'ajax-action'
    style_picto = 'octicon octicon-git-branch'
    style_order = 2
    submission_title = _('Save')
    context = Iidea
    processsecurity_validation = duplicate_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        user = get_current()
        mask = user.get_mask(root) if hasattr(user, 'get_mask') else user
        author = mask if appstruct.pop('anonymous', False) and mask else user
        files = [f['_object_data'] for f in appstruct.pop('attached_files')]
        appstruct['attached_files'] = files
        copy_of_idea = copy(
            context, (root, 'ideas'),
            omit=('created_at', 'modified_at',
                  'opinion', 'examined_at', 'published_at',
                  'len_selections', 'graph'))
        copy_of_idea.opinion = PersistentDict({})
        copy_of_idea.init_graph()
        copy_of_idea.setproperty('originalentity', context)
        copy_of_idea.state = PersistentList(['to work'])
        copy_of_idea.setproperty('author', author)
        grant_roles(user=author, roles=(('Owner', copy_of_idea), ))
        copy_of_idea.set_data(appstruct)
        copy_of_idea.modified_at = datetime.datetime.now(tz=pytz.UTC)
        copy_of_idea.subscribe_to_channel(user)
        copy_of_idea.format(request)
        copy_of_idea.reindex()
        context.reindex()
        request.registry.notify(ActivityExecuted(
            self, [context, copy_of_idea], author))
        return {'newcontext': copy_of_idea}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(kw['newcontext'], "@@index"))


def del_roles_validation(process, context):
    return has_role(role=('Owner', context))


def del_processsecurity_validation(process, context):
    return global_user_processsecurity()


def del_state_validation(process, context):
    return 'archived' in context.state and \
        'version' not in context.state


class DelIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'global-action'
    style_interaction = 'ajax-action'
    style_picto = 'glyphicon glyphicon-trash'
    style_order = 6
    submission_title = _('Continue')
    context = Iidea
    roles_validation = del_roles_validation
    processsecurity_validation = del_processsecurity_validation
    state_validation = del_state_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        request.registry.notify(CorrelableRemoved(object=context))
        root.delfromproperty('ideas', context)
        return {}

    def redirect(self, context, request, **kw):
        root = getSite()
        return HTTPFound(request.resource_url(root))


def edit_roles_validation(process, context):
    return has_role(role=('Owner', context))


def edit_processsecurity_validation(process, context):
    return global_user_processsecurity()


def edit_state_validation(process, context):
    return "to work" in context.state


class EditIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'text-action'
    style_interaction = 'ajax-action'
    style_picto = 'glyphicon glyphicon-pencil'
    style_order = 1
    submission_title = _('Save')
    context = Iidea
    roles_validation = edit_roles_validation
    processsecurity_validation = edit_processsecurity_validation
    state_validation = edit_state_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        user = context.author
        last_version = context.version
        copy_of_idea = copy(
            context,
            (context, 'version'),
            new_name=context.__name__,
            select=('modified_at',),
            omit=('created_at',),
            roles=True)
        copy_of_idea.keywords = context.keywords
        copy_of_idea.setproperty('version', last_version)
        copy_of_idea.setproperty('originalentity', context.originalentity)
        if last_version is not None:
            grant_roles(user=user, roles=(('Owner', last_version), ))

        files = [f['_object_data'] for f in appstruct.pop('attached_files')]
        appstruct['attached_files'] = files
        copy_of_idea.state = PersistentList(['version', 'archived'])
        copy_of_idea.setproperty('author', user)
        note = appstruct.pop('note', '')
        context.note = note
        context.set_data(appstruct)
        context.modified_at = datetime.datetime.now(tz=pytz.UTC)
        copy_of_idea.reindex()
        context.format(request)
        context.reindex()
        if 'archived' in context.state:
            recuperate_actions = getBusinessAction(context,
                                                   request,
                                                   'ideamanagement',
                                                   'recuperate')
            if recuperate_actions:
                recuperate_actions[0].execute(context, request, appstruct, **kw)

        request.registry.notify(ActivityExecuted(self, [context], user))
        return {}

    def redirect(self, context, request, **kw):
        return nothing


def submit_roles_validation(process, context):
    return has_role(role=('Owner', context))


def submit_processsecurity_validation(process, context):
    request = get_current_request()
    if not request.moderate_ideas:
        return False

    if getattr(context, 'originalentity', None):
        originalentity = getattr(context, 'originalentity')
        if originalentity.text == context.text:
            return False
    
    can_submit = getattr(get_current(), 'can_submit_idea', lambda: True)
    return can_submit() and global_user_processsecurity()


def submit_state_validation(process, context):
    return 'to work' in context.state


class SubmitIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'global-action'
    style_interaction = 'ajax-action'
    style_picto = 'glyphicon glyphicon-share'
    style_order = 6
    submission_title = _('Continue')
    context = Iidea
    roles_validation = submit_roles_validation
    processsecurity_validation = submit_processsecurity_validation
    state_validation = submit_state_validation

    def start(self, context, request, appstruct, **kw):
        user = get_current(request)
        context.state = PersistentList(['submitted'])
        context.reindex()
        if hasattr(user, 'add_submission'):
            user.add_submission(context)

        root = getSite()
        # get random moderators
        moderators = get_random_users(ELECTORS_NB, [context.author])
        if not moderators:
            publish_idea_moderation(context, request, root)
        else:
            author = context.author
            start_ballot(
                context, author, request, root,
                moderators, 'ideamoderation')
            alert_data = get_ballot_alert_data(
                context, request, root, moderators)
            alert_data.update(get_user_data(author, 'recipient', request))
            mail_template = root.get_mail_template(
                'content_submit', author.user_locale)
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


def submitmax_processsecurity_validation(process, context):
    request = get_current_request()
    if not request.moderate_ideas:
        return False

    if getattr(context, 'originalentity', None):
        originalentity = getattr(context, 'originalentity')
        if originalentity.text == context.text:
            return False
    
    can_submit = getattr(get_current(), 'can_submit_idea', lambda: True)
    return not can_submit() and global_user_processsecurity()


class SubmitIdeaMax(SubmitIdea):
    style_picto = 'glyphicon glyphicon-share disabled'
    processsecurity_validation = submitmax_processsecurity_validation
    
    def start(self, context, request, appstruct, **kw):
        return {}


def decision_roles_validation(process, context):
    return has_role(role=('Moderator',))


def decision_processsecurity_validation(process, context):
    request = get_current_request()
    if not request.moderate_ideas:
        return False

    return global_user_processsecurity()


def decision_state_validation(process, context):
    return 'submitted' in context.state


class ArchiveIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'global-action'
    style_interaction = 'ajax-action'
    style_picto = 'glyphicon glyphicon-inbox'
    style_order = 4
    submission_title = _('Continue')
    context = Iidea
    roles_validation = decision_roles_validation
    processsecurity_validation = decision_processsecurity_validation
    state_validation = decision_state_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        archive_idea(context, request, root, appstruct)
        remove_ballot_processes(context, request.root['runtime'])
        request.registry.notify(ActivityExecuted(
            self, [context], get_current(request)))
        return {}

    def redirect(self, context, request, **kw):
        return nothing


def pub_roles_validation(process, context):
    return has_role(role=('Owner', context))


def pub_processsecurity_validation(process, context):
    request = get_current_request()
    if request.moderate_ideas:
        return False

    if getattr(context, 'originalentity', None):
        originalentity = getattr(context, 'originalentity')
        if originalentity.text == context.text:
            return False

    return global_user_processsecurity()


def pub_state_validation(process, context):
    return 'to work' in context.state or \
           'submitted' in context.state


class PublishIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'global-action'
    style_interaction = 'ajax-action'
    style_picto = 'glyphicon glyphicon-share'
    style_order = 5
    submission_title = _('Continue')
    context = Iidea
    roles_validation = pub_roles_validation
    processsecurity_validation = pub_processsecurity_validation
    state_validation = pub_state_validation

    def start(self, context, request, appstruct, **kw):
        root = request.root
        if root.support_ideas:
            context.state = PersistentList(['submitted_support', 'published'])
        else:
            context.state = PersistentList(['published', 'submitted_support'])

        context.init_published_at()
        if context.originalentity:
            # Add Nia comment
            alert_comment_nia(
                context.originalentity, request, root,
                internal_kind=InternalAlertKind.content_alert,
                subject_type='idea',
                alert_kind='duplicated',
                duplication=context
                )

        transformed_from = context.transformed_from
        if transformed_from:
            context_type = transformed_from.__class__.__name__.lower()
            # Add Nia comment
            alert_comment_nia(
                transformed_from, request, root,
                internal_kind=InternalAlertKind.content_alert,
                subject_type=context_type,
                alert_kind='transformation_idea',
                idea=context
                )
        
        if getattr(context, '_tree', None):
            tree = getattr(context, '_tree')
            root.merge_tree(tree)

        context.reindex()
        request.registry.notify(ObjectPublished(object=context))
        request.registry.notify(ActivityExecuted(
            self, [context], appstruct.get('user', context.author)))
        return {}

    def redirect(self, context, request, **kw):
        return nothing


def ab_roles_validation(process, context):
    return has_role(role=('Owner', context))


def ab_processsecurity_validation(process, context):
    return global_user_processsecurity()


def ab_state_validation(process, context):
    return 'to work' in context.state


class AbandonIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'global-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'direct'
    style_picto = 'glyphicon glyphicon-stop'
    style_order = 4
    context = Iidea
    roles_validation = ab_roles_validation
    processsecurity_validation = ab_processsecurity_validation
    state_validation = ab_state_validation

    def start(self, context, request, appstruct, **kw):
        context.state = PersistentList(['archived'])
        context.modified_at = datetime.datetime.now(tz=pytz.UTC)
        context.reindex()
        request.registry.notify(ActivityExecuted(
            self, [context], context.author))
        return {}

    def redirect(self, context, request, **kw):
        return nothing


def re_roles_validation(process, context):
    return has_role(role=('Owner', context))


def re_processsecurity_validation(process, context):
    return global_user_processsecurity()


def re_state_validation(process, context):
    return 'archived' in context.state and \
        'version' not in context.state


class RecuperateIdea(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'global-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'direct'
    style_picto = 'glyphicon glyphicon-play'
    style_order = 8
    context = Iidea
    roles_validation = re_roles_validation
    processsecurity_validation = re_processsecurity_validation
    state_validation = re_state_validation

    def start(self, context, request, appstruct, **kw):
        context.state = PersistentList(['to work'])
        context.modified_at = datetime.datetime.now(tz=pytz.UTC)
        context.reindex()
        request.registry.notify(ActivityExecuted(
            self, [context], context.author))
        return {}

    def redirect(self, context, request, **kw):
        return nothing

def comm_roles_validation(process, context):
    return has_role(role=('Member',))


def comm_processsecurity_validation(process, context):
    return global_user_processsecurity()


def comm_state_validation(process, context):
    return 'published' in context.state


class CommentIdea(InfiniteCardinality):
    isSequential = False
    style_descriminator = 'communication-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'sidebar'
    style_interaction_args = 'scroll-bottom'
    style_picto = 'ion-chatbubble'
    style_order = 0
    style_activate = True
    context = Iidea
    roles_validation = comm_roles_validation
    processsecurity_validation = comm_processsecurity_validation
    state_validation = comm_state_validation

    def get_nb(self, context, request):
        user = get_current(request)
        channel = context.channel
        unread_comments = channel.get_comments_between(
            user.get_read_date(channel),
            datetime.datetime.now(tz=pytz.UTC))
        return len(unread_comments)
        # return context.channel.len_comments

    def get_title(self, context, request, nb_only=False):
        len_comments = context.channel.len_comments
        if nb_only:
            return str(len_comments)

        return _("${title} (${number})",
                 mapping={'number': len_comments,
                          'title': request.localizer.translate(self.title)})

    def _get_users_to_alerts(self, context, request, channel):
        users = set(channel.members)
        author = getattr(context, 'author', None)
        context_authors = getattr(
            context, 'authors', [author] if author else [])
        users.update(context_authors)
        return list(users)

    def _alert_users(self, context, request, user, comment):
        root = getSite()
        channel = comment.channel
        users = self._get_users_to_alerts(context, request, channel)
        if user in users:
            users.remove(user)

        author_data = get_user_data(user, 'author', request)
        alert_data = get_entity_data(comment, 'comment', request)
        alert_data.update(author_data)
        alert('internal', [root], users,
              internal_kind=InternalAlertKind.comment_alert,
              subjects=[channel],
              **alert_data)
        subject_data = get_entity_data(context, 'subject', request)
        alert_data.update(subject_data)
        for user_to_alert in [u for u in users if getattr(u, 'email', '')]:
            mail_template = root.get_mail_template(
                'alert_comment', user_to_alert.user_locale)
            subject = mail_template['subject'].format(
                **subject_data)
            email_data = get_user_data(user_to_alert, 'recipient', request)
            email_data.update(alert_data)
            message = mail_template['template'].format(
                novaideo_title=root.title,
                **email_data
            )
            alert('email', [root.get_site_sender()], [user_to_alert.email],
                  subject=subject, body=message)

    def start(self, context, request, appstruct, **kw):
        comment = appstruct['_object_data']
        channel = context.channel
        if channel:
            channel.addtoproperty('comments', comment)
            channel.add_comment(comment)
            comment.format(request)
            comment.state = PersistentList(['published'])
            comment.reindex()
            user = appstruct.get('user', get_current())
            mask = user.get_mask(getSite()) if hasattr(user, 'get_mask') else user
            author = mask if appstruct.get('anonymous', False) and mask else user
            grant_roles(user=author, roles=(('Owner', comment), ))
            if getattr(self, 'subscribe_to_channel', True):
                context.subscribe_to_channel(user)

            comment.setproperty('author', author)
            if appstruct.get('associated_contents', []):
                comment.set_associated_contents(
                    appstruct['associated_contents'], author)

            if appstruct.get('alert', True):
                self._alert_users(context, request, author, comment)

            context.reindex()
            user.set_read_date(channel, datetime.datetime.now(tz=pytz.UTC))

        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, "@@index"))


def comma_roles_validation(process, context):
    return has_role(role=('Anonymous',), ignore_superiors=True)


def comma_processsecurity_validation(process, context):
    return True


class CommentIdeaAnonymous(CommentIdea):
    roles_validation = comma_roles_validation
    processsecurity_validation = comma_processsecurity_validation
    style_interaction = 'ajax-action'
    style_interaction_type = 'popover'
    behavior_id = 'comment_anonymous'

    def start(self, context, request, appstruct, **kw):
        return {}


def present_roles_validation(process, context):
    return has_role(role=('Member',))


def present_processsecurity_validation(process, context):
    return global_user_processsecurity()


def present_state_validation(process, context):
    return 'published' in context.state


class PresentIdea(InfiniteCardinality):
    style_descriminator = 'communication-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'sidebar'
    style_picto = 'glyphicon glyphicon-share-alt'
    style_order = 1
    submission_title = _('Send')
    context = Iidea
    roles_validation = present_roles_validation
    processsecurity_validation = present_processsecurity_validation
    state_validation = present_state_validation

    def get_title(self, context, request, nb_only=False):
        len_members = context.len_contacted
        if nb_only:
            return str(len_members)

        return _("${title} (${number})",
                 mapping={'number': len_members,
                          'title': request.localizer.translate(self.title)})

    def start(self, context, request, appstruct, **kw):
        send_to_me = appstruct['send_to_me']
        members = list(appstruct['members'])
        root = request.root
        user = get_current(request)
        if send_to_me:
            members.append(user)

        userdata = get_user_data(user, 'my', request)
        presentation_subject = appstruct['subject']
        presentation_message = appstruct['message']
        subject = presentation_subject.format(subject_title=context.title)
        users = [m for m in members if not isinstance(m, str)]
        alert('internal', [root], users,
              internal_kind=InternalAlertKind.content_alert,
              subjects=[context], alert_kind='present')
        email_data = get_entity_data(context, 'subject', request)
        email_data.update(userdata)
        for member in members:
            email_member_data = get_user_data(member, 'recipient', request)
            email_member_data.update(email_data)
            member_email = getattr(member, 'email', '') \
                if not isinstance(member, str) else member
            if member_email:
                message = presentation_message.format(
                    novaideo_title=root.title,
                    **email_member_data
                )
                alert('email', [root.get_site_sender()], [member_email],
                      subject=subject, body=message)

            if member is not user and member_email \
               and member_email not in context._email_persons_contacted:
                context._email_persons_contacted.append(
                    member_email)

        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, "@@index"))


def presenta_roles_validation(process, context):
    return has_role(role=('Anonymous',), ignore_superiors=True)


def presenta_processsecurity_validation(process, context):
    return True


class PresentIdeaAnonymous(PresentIdea):
    roles_validation = presenta_roles_validation
    processsecurity_validation = presenta_processsecurity_validation
    style_interaction = 'ajax-action'
    style_interaction_type = 'popover'

    def start(self, context, request, appstruct, **kw):
        return {}


def associate_processsecurity_validation(process, context):
    return (has_role(role=('Owner', context)) or \
           (has_role(role=('Member',)) and 'published' in context.state)) and \
           global_user_processsecurity()


class Associate(InfiniteCardinality):
    context = Iidea
    processsecurity_validation = associate_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        user = get_current(request)
        correlation = appstruct['_object_data']
        correlation.setproperty('source', context)
        correlation.setproperty('author', user)
        root = getSite()
        root.addtoproperty('correlations', correlation)
        objects = list(correlation.targets)
        objects.append(context)
        request.registry.notify(ActivityExecuted(self, objects, user))
        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, "@@index"))


def get_access_key(obj):
    if 'published' in obj.state:
        challenge = getattr(obj, 'challenge', None)
        is_restricted = getattr(challenge, 'is_restricted', False)
        if is_restricted:
            return serialize_roles(
                (('ChallengeParticipant', challenge),
                 'SiteAdmin', 'Admin', 'Moderator'))

        return ['always']
    else:
        return serialize_roles(
            (('Owner', obj), 'SiteAdmin', 'Moderator',
             'Admin', ('LocalModerator', obj)))


def seeidea_processsecurity_validation(process, context):
    challenge = getattr(context, 'challenge', None)
    is_restricted = getattr(challenge, 'is_restricted', False)
    can_access = True
    if is_restricted:
        can_access = has_role(role=('ChallengeParticipant', challenge))

    return can_access and access_user_processsecurity(process, context) and \
           ('published' in context.state or 'censored' in context.state or\
            has_any_roles(
                roles=(('Owner', context), ('LocalModerator', context),
                        'SiteAdmin', 'Moderator')))


@access_action(access_key=get_access_key)
class SeeIdea(InfiniteCardinality):
    """SeeIdea is the behavior allowing access to context"""
    style = 'button' #TODO add style abstract class
    style_descriminator = 'access-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'sidebar'
    style_picto = 'glyphicon glyphicon-eye-open'
    title = _('Details')
    context = Iidea
    actionType = ActionType.automatic
    processsecurity_validation = seeidea_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, "@@index"))


def compare_roles_validation(process, context):
    return has_role(role=('Owner', context))


def compare_processsecurity_validation(process, context):
    return getattr(context, 'version', None) is not None


class CompareIdea(InfiniteCardinality):
    title = _('Compare')
    context = Iidea
    roles_validation = compare_roles_validation
    processsecurity_validation = compare_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, "@@index"))


def opinion_roles_validation(process, context):
    return has_role(role=('Examiner',))


def opinion_processsecurity_validation(process, context):
    request = get_current_request()
    if 'idea' not in request.content_to_examine:
        return False

    return global_user_processsecurity()


def opinion_state_validation(process, context):
    return 'published' in context.state and 'examined' not in context.state


class MakeOpinion(InfiniteCardinality):
    style = 'button' #TODO add style abstract class
    style_descriminator = 'primary-action'
    style_interaction = 'ajax-action'
    style_picto = 'octicon octicon-checklist'
    style_order = 10
    submission_title = _('Save')
    context = Iidea
    roles_validation = opinion_roles_validation
    processsecurity_validation = opinion_processsecurity_validation
    state_validation = opinion_state_validation

    def start(self, context, request, appstruct, **kw):
        appstruct.pop('_csrf_token_')
        context.opinion = PersistentDict(appstruct)
        context.state = PersistentList(
            ['examined', 'published', context.opinion['opinion']])
        context.init_examined_at()
        context.remove_tokens()
        context.reindex()
        member = context.author
        root = getSite()
        users = list(get_users_by_preferences(context))
        users.append(member)
        alert(
            'internal', [root], users,
            internal_kind=InternalAlertKind.examination_alert,
            subjects=[context])
        # Add Nia comment
        alert_comment_nia(
            context, request, root,
            internal_kind=InternalAlertKind.examination_alert,
            subject_type='idea'
            )
        if getattr(member, 'email', ''):
            mail_template = root.get_mail_template(
                'opinion_idea', member.user_locale)
            subject = mail_template['subject'].format(
                subject_title=context.title)
            localizer = request.localizer
            email_data = get_user_data(member, 'recipient', request)
            email_data.update(get_entity_data(context, 'subject', request))
            message = mail_template['template'].format(
                opinion=localizer.translate(_(context.opinion_value)),
                explanation=context.opinion['explanation'],
                novaideo_title=root.title,
                **email_data
            )
            alert('email', [root.get_site_sender()], [member.email],
                  subject=subject, body=message)

        request.registry.notify(ActivityExecuted(
            self, [context], get_current(request)))
        return {}

    def redirect(self, context, request, **kw):
        return nothing


def support_roles_validation(process, context):
    return has_role(role=('Member',))


def support_processsecurity_validation(process, context):
    user = get_current()
    request = get_current_request()
    if not request.support_ideas:
        return False

    return context.evaluation(user) != Evaluations.support and \
           (context.user_has_token(user) or  \
            context.evaluation(user) == Evaluations.oppose) and \
           global_user_processsecurity()


def support_state_validation(process, context):
    return 'published' in context.state and \
        'examined' not in context.state


class SupportIdea(InfiniteCardinality):
    # style = 'button' #TODO add style abstract class
    # style_descriminator = 'text-action'
    # style_picto = 'glyphicon glyphicon-thumbs-up'
    # style_order = 4
    context = Iidea
    roles_validation = support_roles_validation
    processsecurity_validation = support_processsecurity_validation
    state_validation = support_state_validation

    def start(self, context, request, appstruct, **kw):
        user = get_current(request)
        context.init_support_history()
        if context.evaluation(user):
            user.remove_token(context)
            context.remove_token(user)
            context._support_history.append(
                (get_oid(user), datetime.datetime.now(tz=pytz.UTC), -1))

        user.add_token(context, Evaluations.support, request.root)
        context.add_token(user, Evaluations.support)
        context._support_history.append(
            (get_oid(user), datetime.datetime.now(tz=pytz.UTC), 1))
        context.reindex()
        request.registry.notify(ActivityExecuted(self, [context], user))
        if user is not context.author:
            alert('internal', [request.root], [context.author],
                  internal_kind=InternalAlertKind.support_alert,
                  subjects=[context], support_kind='support')

        return {}

    def redirect(self, context, request, **kw):
        return nothing


def oppose_processsecurity_validation(process, context):
    user = get_current()
    request = get_current_request()
    if not request.support_ideas:
        return False

    return context.evaluation(user) != Evaluations.oppose and \
           (context.user_has_token(user) or  \
            context.evaluation(user) == Evaluations.support) and \
           global_user_processsecurity()


class OpposeIdea(InfiniteCardinality):
    # style = 'button' #TODO add style abstract class
    # style_descriminator = 'text-action'
    # style_picto = 'glyphicon glyphicon-thumbs-down'
    # style_order = 5
    context = Iidea
    roles_validation = support_roles_validation
    processsecurity_validation = oppose_processsecurity_validation
    state_validation = support_state_validation

    def start(self, context, request, appstruct, **kw):
        user = get_current(request)
        context.init_support_history()
        if context.evaluation(user):
            user.remove_token(context)
            context.remove_token(user)
            context._support_history.append(
                (get_oid(user), datetime.datetime.now(tz=pytz.UTC), -1))

        user.add_token(context, Evaluations.oppose, request.root)
        context.add_token(user, Evaluations.oppose)
        context._support_history.append(
            (get_oid(user), datetime.datetime.now(tz=pytz.UTC), 0))
        context.reindex()
        request.registry.notify(ActivityExecuted(self, [context], user))
        if user is not context.author:
            alert('internal', [request.root], [context.author],
                  internal_kind=InternalAlertKind.support_alert,
                  subjects=[context], support_kind='oppose')

        return {}

    def redirect(self, context, request, **kw):
        return nothing


def withdrawt_processsecurity_validation(process, context):
    return context.evaluation(get_current()) and \
           global_user_processsecurity()


class WithdrawToken(InfiniteCardinality):
    # style = 'button' #TODO add style abstract class
    # style_descriminator = 'text-action'
    # style_picto = 'glyphicon glyphicon-share-alt'
    # style_order = 6
    context = Iidea
    roles_validation = support_roles_validation
    processsecurity_validation = withdrawt_processsecurity_validation
    state_validation = support_state_validation

    def start(self, context, request, appstruct, **kw):
        user = get_current(request)
        user.remove_token(context)
        context.remove_token(user)
        context.init_support_history()
        context._support_history.append(
            (get_oid(user), datetime.datetime.now(tz=pytz.UTC), -1))
        context.reindex()
        request.registry.notify(ActivityExecuted(self, [context], user))
        if user is not context.author:
            alert('internal', [request.root], [context.author],
                  internal_kind=InternalAlertKind.support_alert,
                  subjects=[context], support_kind='withdraw')

        return {}

    def redirect(self, context, request, **kw):
        return nothing


def seewgs_state_validation(process, context):
    request = get_current_request()
    if 'proposal' not in request.content_to_manage:
        return False

    if 'idea' in request.content_to_examine:
        return 'favorable' in context.state
    else:
        return 'published' in context.state


class SeeRelatedWorkingGroups(InfiniteCardinality):
    style_descriminator = 'listing-primary-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'slider'
    style_picto = 'glyphicon glyphicon-link'
    style_order = 2
    context = Iidea
    #processsecurity_validation = seeideas_processsecurity_validation
    #roles_validation = seeideas_roles_validation
    state_validation = seewgs_state_validation

    def start(self, context, request, appstruct, **kw):
        return {}

    def redirect(self, context, request, **kw):
        return nothing

# Idea moderation

def decision_state_validation(process, context):
    return 'submitted' in context.state


class ModerationVote(StartBallot):
    context = Iidea
    state_validation = decision_state_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        moderators = self.process.execution_context.get_involved_collection(
            'electors')
        alert(
            'internal', [root], moderators,
            internal_kind=InternalAlertKind.moderation_alert,
            subjects=[context], alert_kind='moderate_content')
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
                'moderate_content', moderator.user_locale)
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
        idea = self.process.execution_context.involved_entity(
            'content')
        close_ballot(self, idea, request)
        # idea not removed
        if idea and idea.__parent__:
            root = getSite()
            moderators = self.process.execution_context.get_involved_collection(
                'electors')
            for moderator in moderators:
                revoke_roles(
                    user=moderator,
                    roles=(('LocalModerator', idea),))

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
                publish_idea_moderation(
                    idea, request, root,
                    ballot_url=ballot_url if accepted is not _marker else None)
            else:
                archive_idea(
                    idea, request, root, {'explanation': ''},
                    ballot_url=ballot_url)

        super(ModerationVote, self).after_execution(
            idea, request, **kw)

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, "@@index"))

#TODO behaviors

VALIDATOR_BY_CONTEXT[Idea] = {
    'action': CommentIdea,
    'see': SeeIdea,
    'access_key': get_access_key
}
