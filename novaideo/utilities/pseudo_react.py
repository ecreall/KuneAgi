# -*- coding: utf8 -*-
# Copyright (c) 2016 by Ecreall under licence AGPL terms
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi
import json
from pyramid.threadlocal import get_current_registry
from pyramid import renderers
from pyramid.httpexceptions import HTTPFound
from pyramid.traversal import find_resource

from substanced.util import get_oid

from daceui.interfaces import IDaceUIAPI
from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from dace.objectofcollaboration.principal.util import (
    get_current)
from dace.util import (
    getAllBusinessAction, find_catalog,
    get_obj)

from novaideo import _, nothing, log
from novaideo.views.idea_management.comment_idea import (
    CommentsView)
from novaideo.views.user_management.discuss import (
    DiscussCommentsView,
    GeneralCommentsView)
from novaideo.views.idea_management.present_idea import (
    SentToView)
from novaideo.views.novaideo_view_manager.see_my_supports import (
    CONTENTS_MESSAGES)
from novaideo.views.novaideo_view_manager.see_my_selections import (
    CONTENTS_MESSAGES as SELECT_CONTENTS_MESSAGES)
from novaideo.views.novaideo_view_manager.see_my_contents import (
    CONTENTS_MESSAGES as MY_CONTENTS_MESSAGES)
from novaideo.views.novaideo_view_manager.see_my_participations import (
    CONTENTS_MESSAGES as MY_PARTICIPATIONS_MESSAGES)
from novaideo.views.user_management.see_registrations import (
    CONTENTS_MESSAGES as REGISTRATION_CONTENTS_MESSAGES)
from novaideo.views.invitation_management.see_invitations import (
    CONTENTS_MESSAGES as INVITATION_CONTENTS_MESSAGES)
from novaideo.views.organization_management.see_organizations import (
    CONTENTS_MESSAGES as ORGANIZATION_CONTENTS_MESSAGES)
from novaideo.utilities.util import (
    update_all_ajax_action, render_listing_obj,
    render_index_obj, render_view_obj, render_view_comment)
from novaideo.views.filter import find_entities
from novaideo.content.interface import (
    IPreregistration, IInvitation, IOrganization,
    Iidea)
from novaideo.content.organization import Organization
from novaideo.content.proposal import Proposal
from novaideo.core import can_access


def _get_resources_to_include(request, resources, currents):
    result = []

    def add_resource(type_):
        for source in resources[type_+'_links']:
            source_url = request.static_url(source)
            if source_url not in currents:
                url = type_ + '@' + source_url
                if url not in result:
                    result.append(url)
    if resources:
        add_resource('css')
        add_resource('js')

    return result


def _render_obj_view(id_, user, request):
    if request.POST:
        request.POST.clear()

    request.invalidate_cache = True
    type_, oid = id_.split('_')
    try:
        obj = get_obj(int(oid))
        if obj:
            if type_ == 'listing':
                return {id_+'.body': render_listing_obj(
                    request, obj, user)}

            if type_ == 'listingbloc':
                return {id_+'.body': render_listing_obj(
                    request, obj, user, view_type='bloc')}

            if type_ == 'index':
                return {id_+'.body': render_index_obj(
                    request, obj, user)}

            if type_ == 'comment':
                return {id_+'.body': render_view_comment(
                    request, obj)}

            return {id_+'.body': render_view_obj(
                request, obj, type_)}
        else:
            return {id_+'.delated': True}

    except Exception as error:
        log.warning(error)
        return {id_+'.delated': True}


def update_contextual_help(request, context, user, view_name, contextual_help):
    from novaideo.contextual_help_messages import render_contextual_help
    messages = render_contextual_help(
        request, context, user, view_name)
    return {contextual_help[0]+'.body': renderers.render(
        'novaideo:views/templates/panels/contextual_help.pt',
        {'messages': messages,
         'condition': True},
        request)}


def update_steps_navbar(request, context, steps_navbars):
    from novaideo.steps import steps_panels
    result = steps_panels(context, request)
    return {steps_navbars[0]+'.body': renderers.render(
        'novaideo:views/templates/panels/steps.pt',
        result,
        request)}


def get_all_updated_data(action, request, context, api, **kwargs):
    result = {'action': None, 'view': api}
    if not action:
        return result

    metadatagetter = METADATA_GETTERS.get(
        action.process_id + '.' + action.node_id, None)
    current_resources = api.params('included_resources')
    current_resources = json.loads(current_resources) \
        if current_resources else []
    resources = kwargs.get('resources', None)
    object_views = api.params('object_views')
    object_views = json.loads(object_views) if object_views else []
    counters = api.params('counters')
    counters = json.loads(counters) if counters else []
    contextual_help = api.params('contextual_help')
    contextual_help = json.loads(contextual_help) if contextual_help else []
    steps_navbars = api.params('steps_navbars')
    steps_navbars = json.loads(steps_navbars) if steps_navbars else []
    object_views_to_update = []
    if metadatagetter:
        user = get_current()
        source_path = api.params('source_path')
        source_context = None
        if source_path:
            kwargs['source_path'] = source_path
            source_path = '/'.join(source_path.split('/')[:-1])
            try:
                source_context = find_resource(request.root, source_path)
                kwargs['source_context'] = source_context
            except Exception:
                kwargs['source_context'] = context

        kwargs['is_source_context'] = not source_context or \
            context is source_context
        kwargs['user'] = user
        kwargs['object_views'] = object_views
        kwargs['view_name'] = api.params('view_name')
        result = metadatagetter(action, request, context, api, **kwargs)
        #update views: listing view, index view
        result_ovtu = result.get('object_views_to_update', [])
        #include listingbloc
        for ovtu in list(result_ovtu):
            if ovtu.startswith('listing_'):
                result_ovtu.append(
                    ovtu.replace('listing_', 'listingbloc_'))

        object_views_to_update = [o for o in result_ovtu
                                  if o in kwargs['object_views']]
        for obj_id in object_views_to_update:
            result.update(_render_obj_view(
                obj_id, user, request))

        #update object to hide: include listingbloc component
        for ovth in list(result.get('objects_to_hide', [])):
            if ovth.startswith('listing_'):
                result['objects_to_hide'].append(
                    ovth.replace('listing_', 'listingbloc_'))

        #update couters
        counters_to_update = [c for c in result.get('counters-to-update', [])
                              if c in counters]
        for count_op_id in counters_to_update:
            count_op = COUNTERS_COMPONENTS.get(count_op_id, None)
            if count_op:
                result.update(count_op(action, request, context, api, **kwargs))

        #update contextualhelp
        if context is source_context and contextual_help:
            result['contextualhelp_to_update'] = contextual_help
            result.update(update_contextual_help(
                request, context, user, kwargs['view_name'], contextual_help))

        #update steps navbar
        if context is source_context and steps_navbars:
            result['stepsnavbars_to_update'] = steps_navbars
            result.update(update_steps_navbar(
                request, context, steps_navbars))

    result['resources'] = _get_resources_to_include(
        request, resources, current_resources)
    return result


def get_components_data(action, view, **kwargs):
    kwargs['action_id'] = action
    return kwargs


def get_default_action_metadata(action, request, context, api, **kwargs):
    redirect_url = None
    body = None
    if 'view_data' in kwargs:
        view_instance, view_result = kwargs['view_data']
        if view_result and view_result is not nothing:
            if isinstance(view_result, HTTPFound):
                redirect_url = view_result.headers['location']
            else:
                body = view_result['coordinates'][view_instance.coordinates][0]['body']

    result = {
        'action': 'redirect_action',
        'view': api,
        'redirect_url': redirect_url,
        'new_body': json.dumps(body) if body else None
    }
    return result


def get_edit_entity_metadata(
    action, request, context, api,
    msg=None, viewname=None, **kwargs):
    alert_msg = None
    redirect_url = None
    is_excuted = False
    object_views_to_update = []
    body = None
    if 'view_data' in kwargs:
        view_instance, view_result = kwargs['view_data']
        if view_result:
            if isinstance(view_result, HTTPFound) or view_result is nothing:
                is_excuted = True
                alert_msg = msg
                oid = get_oid(context, None)
                object_views_to_update = [
                    'listing_'+str(oid),
                    'index_'+str(oid),
                ]
                if view_result is not nothing:
                    redirect_url = view_result.headers['location']
            else:
                body = view_result['coordinates'][view_instance.coordinates][0]['body']

    result = {
        'action': 'redirect_action',
        'view': api,
        'redirect_url': redirect_url,
        'view_name': viewname,
        'object_views_to_update': object_views_to_update,
        'new_body': json.dumps(body) if body else None
    }
    result['alert_msg'] = request.localizer.translate(alert_msg) if alert_msg else None
    result['alert_type'] = 'success'
    result['is_excuted'] = is_excuted
    return result


def get_dirct_edit_entity_metadata(
    action, request, context, api,
    msg=None, viewname=None, **kwargs):
    alert_msg = None
    redirect_url = None
    alert_msg = msg
    object_views_to_update = []
    oid = get_oid(context, None)
    object_views_to_update = [
        'listing_'+str(oid),
        'index_'+str(oid),
    ]
    result = {
        'action': 'redirect_action',
        'view': api,
        'redirect_url': redirect_url,
        'view_name': viewname,
        'object_views_to_update': object_views_to_update,
    }
    result['alert_msg'] = request.localizer.translate(alert_msg) if alert_msg else None
    result['alert_type'] = 'success'
    return result


def get_subscribtion_metadata(action, request, context, api, **kwargs):
    alert_msg = _("Vous n'êtes plus abonné à la discussion.")
    opposit_action = 'subscribe'
    removed = True
    if action.node_id == 'subscribe':
        removed = False
        alert_msg = _('Vous êtes maintenant abonné à la discussion.')
        opposit_action = 'unsubscribe'

    opposit_actions = getAllBusinessAction(
        context, request,
        process_id='channelmanagement',
        node_id=opposit_action,
        process_discriminator='Application')
    result = {
        'action': 'dropdown_action',
        'view': api,
    }
    subject = context.subject
    user = kwargs.get('user', None)
    new_channel = ''
    if subject:
        actions_call, action_resources = update_all_ajax_action(
            subject, request, 'comment')
        if actions_call:
            object_values = {
                'object': context,
                'current_user': user,
                'action_call': actions_call[0]}
            new_channel = renderers.render(
                context.templates.get('default'),
                object_values,
                request)

    if opposit_actions:
        opposit_action = opposit_actions[0]
        dace_ui_api = get_current_registry().getUtility(
            IDaceUIAPI, 'dace_ui_api')
        opposit_action_inf = dace_ui_api.action_infomrations(
            opposit_action, context, request)
        actionoid = str(getattr(action, '__oid__', 'entityoid'))
        oppositactionoid = str(getattr(
            opposit_action, '__oid__', 'entityoid'))
        contextoid = str(getattr(
            context, '__oid__', 'entityoid'))
        action_view = DEFAULTMAPPING_ACTIONS_VIEWS[opposit_action.__class__]
        action_view_title = action_view.title

        result.update({
            'components': [actionoid + '-' + contextoid],
            'action_title': request.localizer.translate(opposit_action.title),
            'action_icon': getattr(opposit_action, 'style_picto', ''),
            'action_view_title': request.localizer.translate(action_view_title),
            'new_components': [new_channel],
            'removed': removed,
            'has_opposit': True,
            'new_component_id': oppositactionoid + '-' + contextoid,
            'opposit_action_id': opposit_action_inf.get('action_id'),
            'opposit_actionurl_update': opposit_action_inf.get(
                'actionurl_update'),
            'opposit_actionurl_after': opposit_action_inf.get('after_url'),
            'alert_msg': request.localizer.translate(alert_msg),
            'alert_type': 'success'
        })

    return result


def get_selection_metadata(action, request, context, api, **kwargs):
    opposit_action = 'select'
    alert_msg = _('${context} ne fait maintenant plus partie de vos suivis.',
                  mapping={'context': context.title})
    objects_to_hide = []
    if action.node_id == 'select':
        opposit_action = 'deselect'
        alert_msg = _('${context} fait maintenant partie de vos suivis.',
                      mapping={'context': context.title})
    else:
        view_name = 'seemyselections'
        source_view_name = kwargs.get('view_name', '')
        if source_view_name == view_name:
            objects_to_hide = ['listing_'+str(get_oid(context, None))]

    opposit_actions = getAllBusinessAction(
        context, request,
        process_id='novaideoabstractprocess',
        node_id=opposit_action,
        process_discriminator='Application')
    result = {
        'action': 'footer_action',
        'view': api,
    }
    if opposit_actions:
        localizer = request.localizer
        opposit_action = opposit_actions[0]
        dace_ui_api = get_current_registry().getUtility(
            IDaceUIAPI, 'dace_ui_api')
        opposit_action_inf = dace_ui_api.action_infomrations(
            opposit_action, context, request)
        actionoid = str(getattr(action, '__oid__', 'entityoid'))
        oppositactionoid = str(getattr(
            opposit_action, '__oid__', 'entityoid'))
        contextoid = str(getattr(
            context, '__oid__', 'entityoid'))
        len_selection = getattr(context, 'len_selections', 0)
        action_view = DEFAULTMAPPING_ACTIONS_VIEWS[opposit_action.__class__]
        action_view_title = action_view.title
        result.update({
            'components': [actionoid + '-' + contextoid],
            'action_item_nb': len_selection,
            'action_title': localizer.translate(opposit_action.title),
            'action_view_title': localizer.translate(action_view_title),
            'action_icon': getattr(opposit_action, 'style_picto', ''),
            'objects_to_hide': objects_to_hide,
            'has_opposit': True,
            'new_component_id': oppositactionoid + '-' + contextoid,
            'opposit_action_id': opposit_action_inf.get('action_id'),
            'opposit_actionurl_update': opposit_action_inf.get(
                'actionurl_update'),
            'opposit_actionurl_after': opposit_action_inf.get('after_url'),
            'alert_msg': localizer.translate(alert_msg),
            'alert_type': 'success'
        })

    result['counters-to-update'] = ['component-navbar-myselections']

    return result


def get_support_metadata(action, request, context, api, **kwargs):
    node_id = action.node_id
    objects_to_hide = []
    alert_msg = None
    if node_id == 'oppose':
        alert_msg = _('Vous êtes maintenant opposé au contenu ${context}.',
                      mapping={'context': context.title})
    elif node_id == 'support':
        alert_msg = _('Vous soutenez maintenant le contenu ${context}.',
                      mapping={'context': context.title})
    elif node_id == 'withdraw_token':
        alert_msg = _('Votre jeton est bien récupéré du contenu ${context}.',
                      mapping={'context': context.title})

    localizer = request.localizer
    contextoid = str(getattr(
        context, '__oid__', 'entityoid'))
    if action.node_id == 'withdraw_token':
        view_name = 'seemysupports'
        source_view_name = kwargs.get('view_name', '')
        if source_view_name == view_name:
            objects_to_hide = ['listing_'+str(get_oid(context, None))]

    result = {
        'components': [contextoid],
        'action': 'support_action',
        'view': api,
        'objects_to_hide': objects_to_hide,
        'alert_msg': localizer.translate(alert_msg),
        'alert_type': 'success'
    }

    result['counters-to-update'] = ['component-navbar-mysupports']
    return result

# User


def get_deactivate_profile_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le profil a bien été désactivé."),
        **kwargs)
    source_view_name = kwargs.get('view_name', '')
    view_name = 'seeusers'
    if result.get('is_excuted'):
        if source_view_name != view_name:
            result['objects_to_hide'] = [
                'listing_'+str(get_oid(context, None))]

        result['counters-to-update'] = [
            'person-proposals-counter',
            'component-navbar-myparticipations'
        ]

    return result

#Chanels

def get_comment_metadata(action, request, context, api, **kwargs):
    body = None
    if 'view_data' in kwargs:
        comments = [context.channel.comments[-1]]
        result_view = CommentsView(context, request)
        result_view.comments = comments
        body = result_view.update()['coordinates'][result_view.coordinates][0]['body']

    actionoid = str(getattr(action, '__oid__', 'entityoid'))
    contextoid = str(getattr(
        context, '__oid__', 'entityoid'))
    result = {
        'action': 'footer_action',
        'view': api,
        'components': [actionoid + '-' + contextoid],
        'action_item_nb': context.channel.len_comments,
        'action_title': request.localizer.translate(action.title),
        'action_icon': getattr(action, 'style_picto', ''),
        'new_body': body,
        'object_views_to_update': [
            'listing_'+contextoid,
            'comment_'+contextoid]
    }
    return result


def get_edit_comment_metadata(action, request, context, api, **kwargs):
    status = False
    if 'view_data' in kwargs:
        status = True

    contextoid = str(get_oid(context, None))
    result = {
        'action': 'footer_action',
        'view': api,
        'status': status,
        'object_views_to_update': [
            'listing_'+contextoid,
            'comment_'+contextoid]
        }

    return result


def get_remove_comment_metadata(action, request, context, api, **kwargs):
    result = {
        'action': 'footer_action',
        'view': api}
    channel = kwargs.get('channel')
    if context:
        comment_actions = getAllBusinessAction(
            context, request, node_id='comment',
            process_discriminator='Application')
        comment_actions.extend(getAllBusinessAction(
            context, request, node_id='discuss',
            process_discriminator='Application'))
        if comment_actions:
            action = comment_actions[0]
            actionoid = str(getattr(action, '__oid__', 'entityoid'))
            contextoid = str(getattr(
                context, '__oid__', 'entityoid'))
            result.update({
                'components': [actionoid + '-' + contextoid],
                'action_item_nb': channel.len_comments,
                'action_title': request.localizer.translate(action.title),
                'action_icon': getattr(action, 'style_picto', ''),
                'alert_msg': request.localizer.translate(
                    _('Le commentaire est maintenant supprimé.')),
                'alert_type': 'success'
            })
    result['object_views_to_update'] = [
        'listing_'+str(kwargs.get('comment_oid', None)),
        'comment_'+str(kwargs.get('comment_oid', None))]
    comment_parent = kwargs.get('comment_parent', None)
    if comment_parent:
        parent_oid = str(get_oid(comment_parent, None))
        result['object_views_to_update'].extend(
            ['comment_'+parent_oid,
             'listing_'+parent_oid])

    return result


def get_general_discuss_metadata(action, request, context, api, **kwargs):
    body = None
    if 'view_data' in kwargs:
        channel = context.channel
        comments = [channel.comments[-1]]
        result_view = GeneralCommentsView(context, request)
        result_view.comments = comments
        body = result_view.update()['coordinates'][result_view.coordinates][0]['body']

    contextoid = str(get_oid(context, None))
    result = {
        'action': 'footer_action',
        'view': api,
        'new_body': body,
        'object_views_to_update': [
            'listing_'+contextoid,
            'comment_'+contextoid,
            ]
        }
    return result


def get_discuss_metadata(action, request, context, api, **kwargs):
    body = None
    channel = None
    if 'view_data' in kwargs:
        user = kwargs.get('user', None)
        channel = context.get_channel(user)
        comments = [channel.comments[-1]]
        result_view = DiscussCommentsView(context, request)
        result_view.comments = comments
        body = result_view.update()['coordinates'][result_view.coordinates][0]['body']

    actionoid = str(getattr(action, '__oid__', 'entityoid'))
    contextoid = str(getattr(
        context, '__oid__', 'entityoid'))
    if not channel:
        channel = kwargs.get('channel', None)

    result = {
        'action': 'footer_action',
        'view': api,
        'components': [actionoid + '-' + contextoid],
        'action_item_nb': getattr(channel, 'len_comments', 0),
        'action_title': request.localizer.translate(action.title),
        'action_icon': getattr(action, 'style_picto', ''),
        'new_body': body,
        'object_views_to_update': [
            'listing_'+contextoid,
            'comment_'+contextoid]
    }
    return result


def get_respond_metadata(action, request, context, api, **kwargs):
    body = None
    if 'view_data' in kwargs:
        request.POST.clear()
        comments = [context.comments[-1]]
        result_view = CommentsView(context, request)
        result_view.comments = comments
        body = result_view.update()['coordinates'][result_view.coordinates][0]['body']

    channel = context.channel
    subject = channel.subject
    result = {
        'action': 'footer_action',
        'view': api,
        'new_body': body}
    if subject:
        comment_actions = getAllBusinessAction(
            subject, request, node_id='comment',
            process_discriminator='Application')
        comment_actions.extend(getAllBusinessAction(
            subject, request, node_id='discuss',
            process_discriminator='Application'))
        if comment_actions:
            action = comment_actions[0]
            actionoid = str(getattr(action, '__oid__', 'entityoid'))
            contextoid = str(getattr(
                subject, '__oid__', 'entityoid'))
            result.update({
                'components': [actionoid + '-' + contextoid],
                'action_item_nb': channel.len_comments,
                'action_title': request.localizer.translate(action.title),
                'action_icon': getattr(action, 'style_picto', ''),
            })

    contextoid = str(get_oid(context))
    result['object_views_to_update'] = [
        'listing_'+contextoid,
        'comment_'+contextoid]
    return result


def get_tranform_into_idea_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request, context, api,
        _("Le commentaire a bien été tranformé en une idée."),
        **kwargs)
    result['counters-to-update'] = [
        'component-navbar-mycontents',
        'novideo-contents-ideas',
        'home-ideas-counter'
        ]
    return result


def get_present_metadata(action, request, context, api, **kwargs):
    body = None
    if 'view_data' in kwargs:
        result_view = SentToView(context, request)
        body = result_view.update()['coordinates'][result_view.coordinates][0]['body']

    actionoid = str(getattr(action, '__oid__', 'entityoid'))
    contextoid = str(getattr(
        context, '__oid__', 'entityoid'))
    result = {
        'action': 'footer_action',
        'view': api,
        'components': [actionoid + '-' + contextoid],
        'action_item_nb': context.len_contacted,
        'action_title': request.localizer.translate(action.title),
        'action_icon': getattr(action, 'style_picto', ''),
        'new_body': body
    }
    return result


def get_withdraw_user_metadata(action, request, context, api, **kwargs):
    source_context = kwargs.get('source_context', None)
    redirect_url = None
    alert_msg = None
    executed = False
    object_views_to_update = []
    objects_to_hide = []
    if source_context:
        if isinstance(source_context, Organization):
            objects_to_hide = ['listing_'+str(get_oid(context, None))]
            executed = True
        elif 'view_data' in kwargs:
            view_instance, view_result = kwargs['view_data']
            if view_result:
                if view_result is nothing:
                    executed = True
                    oid = get_oid(context, None)
                    object_views_to_update = [
                        'listing_'+str(oid),
                        'index_'+str(oid),
                    ]
                elif isinstance(view_result, HTTPFound):
                    executed = True
                    redirect_url = view_result.headers['location']

    if executed:
        alert_msg = _("Le membre ${context} est bien retiré de l'organisation.",
                      mapping={'context': context.title})
    result = {
        'action': 'redirect_action',
        'view': api,
        'redirect_url': redirect_url,
        'objects_to_hide': objects_to_hide,
        'view_name': 'index',
        'object_views_to_update': object_views_to_update,
        'new_body': None,
        'alert_msg': request.localizer.translate(alert_msg) if alert_msg else None,
        'alert_type': 'success'
    }
    return result


def get_comment_pin_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le commentaire a bien été épinglé."),
        **kwargs)
    contextoid = str(get_oid(context, None))
    result['object_views_to_update'] = [
        'listing_'+contextoid,
        'comment_'+contextoid
    ]
    return result


def get_comment_unpin_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le commentaire a bien été détaché."),
        **kwargs)
    contextoid = str(get_oid(context, None))
    result['object_views_to_update'] = [
        'listing_'+contextoid,
        'comment_'+contextoid
    ]
    return result

#Invitations

def get_remove_invitation_metadata(action, request, context, api, **kwargs):
    redirect_url = None
    view_name = 'seeinvitations'
    redirect_url = request.resource_url(request.root, '@@'+view_name)
    user = kwargs.get('user', None)
    objects = find_entities(
        user=user,
        interfaces=[IInvitation])
    len_result = len(objects)
    index = str(len_result)
    oid = get_oid(context, None)
    object_views_to_update = [
        'listing_'+str(oid),
        'index_'+str(oid),
    ]
    if len_result > 1:
        index = '*'

    view_title = request.localizer.translate(
        _(INVITATION_CONTENTS_MESSAGES[index],
          mapping={'nember': len_result}))
    result = {
        'action': 'redirect_action',
        'view': api,
        'redirect_url': redirect_url,
        'view_title': view_title,
        'object_views_to_update': object_views_to_update,
        'ignore_redirect': not kwargs['is_source_context'],
        'view_name': view_name,
    }
    result['alert_msg'] = request.localizer.translate(
        _("L'invitation a bien été supprimée."))
    result['alert_type'] = 'success'
    return result


def get_edit_invitation_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request, context, api,
        _("L'invitation a bien été modifiée."),
        'seeinvitations', **kwargs)
    return result


def get_remind_invitation_metadata(action, request, context, api, **kwargs):
    return get_dirct_edit_entity_metadata(
        action, request, context, api,
         _("L'invité ${context} a bien été rappelé.",
          mapping={'context': context.first_name + ' ' + context.last_name}),
        'seeinvitations', **kwargs)


def get_refuse_invitation_metadata(action, request, context, api, **kwargs):
    return get_dirct_edit_entity_metadata(
        action, request, context, api,
         _("L'invité ${context} a bien été réfusée.",
          mapping={'context': context.first_name + ' ' + context.last_name}),
        'seeinvitations', **kwargs)


def get_report_entity_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le contenu a bien été signalé."),
        **kwargs)
    if result.get('is_excuted'):
        context_id = str(get_oid(context, None))
        result['object_views_to_update'] = [
            'listing_'+context_id,
            'index_'+context_id,
            'seereports_'+context_id,
            'comment_'+context_id]

    return result


def get_ignore_entity_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("Les signalisations ont bien été ignorées."),
        **kwargs)
    if result.get('is_excuted'):
        context_id = str(get_oid(context, None))
        result['object_views_to_update'] = [
            'listing_'+context_id,
            'index_'+context_id,
            'seereports_'+context_id,
            'comment_'+context_id]

    return result


def get_censor_entity_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le contenu a bien été censuré."),
        **kwargs)
    if result.get('is_excuted'):
        source_view_name = kwargs.get('view_name', '')
        context_id = str(get_oid(context, None))
        result['object_views_to_update'] = [
            'index_'+context_id,
            'listing_'+context_id,
            'seereports_'+context_id,
            'comment_'+context_id
        ]
        view_name = 'seemycontents'
        if source_view_name != view_name:
            result['objects_to_hide'] = [
                'listing_'+context_id]
            result['counters-to-update'] = [
                'home-ideas-counter',
                'person-ideas-counter',
                'novideo-contents-ideas'
            ]

    return result


def get_restor_entity_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le contenu a bien été restoré."),
        **kwargs)
    if result.get('is_excuted'):
        context_id = str(get_oid(context, None))
        result['object_views_to_update'] = [
            'listing_'+context_id,
            'index_'+context_id,
            'seereports_'+context_id,
            'comment_'+context_id]
        result['counters-to-update'] = [
            'person-ideas-counter'
        ]

    return result

#Registrations

def get_remind_registration_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request, context, api,
        _("L'inscrit ${context} a bien été rappelé.",
        mapping={'context': getattr(context, 'title', context.__name__)}),
        'seeregistrations', **kwargs)


def get_accept_registration_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request, context, api,
        _("L'inscription de ${context} a bien été accepter.",
          mapping={'context': getattr(context, 'title', context.__name__)}),
        'seeregistrations', **kwargs)


def get_remove_registration_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request, context, api,
        _("L'inscription a bien été supprimée."),
        'seeregistrations', **kwargs)
    user = kwargs.get('user', None)
    registrations = find_entities(
        user=user,
        interfaces=[IPreregistration])
    len_result = len(registrations)
    index = str(len_result)
    if len_result > 1:
        index = '*'

    view_title = request.localizer.translate(
        _(REGISTRATION_CONTENTS_MESSAGES[index],
          mapping={'nember': len_result}))
    result['ignore_redirect'] = not kwargs['is_source_context']
    result['view_title'] = view_title
    return result

# Smart folders


def get_edit_folder_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le dossier a bien été modifié."),
        **kwargs)


def get_remove_folder_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request, context, api,
        _("Le dossier a bien été supprimé."),
        **kwargs)
    result['ignore_redirect'] = not kwargs['is_source_context']
    return result


def get_publish_folder_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le dossier a bien été publié."),
        **kwargs)


def get_archive_folder_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le dossier a bien été retiré."),
        **kwargs)


def get_add_subfolder_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le sous dossier a bien été ajouté."),
        **kwargs)

#Ideas

def get_archive_idea_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("L'idée a bien été archivée."),
        **kwargs)
    source_view_name = kwargs.get('view_name', '')
    view_name = 'seemycontents'
    if result.get('is_excuted') and source_view_name != view_name:
        result['objects_to_hide'] = [
            'listing_'+str(get_oid(context, None))]
        result['counters-to-update'] = [
            'home-ideas-counter',
            'person-ideas-counter',
            'novideo-contents-ideas'
        ]

    return result


def get_submit_idea_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("L'idée a bien été soumise à modération."),
        **kwargs)


def get_publish_idea_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("L'idée a bien été publiée."),
        **kwargs)


def get_opinion_idea_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("L'idée a bien été examinée."),
        **kwargs)
    result['counters-to-update'] = [
        'component-navbar-mysupports'
        ]
    return result


def get_edit_idea_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("L'idée a bien été modifiée."),
        **kwargs)


def get_dirct_archive_idea_metadata(action, request, context, api, **kwargs):
    result = get_dirct_edit_entity_metadata(
        action, request,
        context, api,
        _("L'idée a bien été archivée."),
        **kwargs)
    source_view_name = kwargs.get('view_name', '')
    view_name = 'seemycontents'
    if source_view_name != view_name:
        result['objects_to_hide'] = [
            'listing_'+str(get_oid(context, None))]

    return result


def get_dirct_recuperate_idea_metadata(action, request, context, api, **kwargs):
    return get_dirct_edit_entity_metadata(
        action, request,
        context, api,
        _("L'idée a bien été récupérée."),
        **kwargs)


def get_dirct_edit_idea_metadata(action, request, context, api, **kwargs):
    return get_dirct_edit_entity_metadata(
        action, request,
        context, api,
        _("L'idée a bien été modifiée."),
        **kwargs)


def get_remove_idea_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request, context, api,
        _("L'idée a bien été supprimée."),
        **kwargs)
    result['ignore_redirect'] = not kwargs['is_source_context']
    result['counters-to-update'] = [
        'component-navbar-mycontents'
        ]
    return result


def get_create_idea_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request, context, api,
        _("L'idée a bien été créée."),
        **kwargs)
    result['counters-to-update'] = [
        'component-navbar-mycontents',
        'novideo-contents-ideas',
        'home-ideas-counter'
        ]
    return result


#Proposals

def get_submit_proposal_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("La proposition a bien été soumise à modération."),
        **kwargs)


def get_publish_proposal_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("La modération a bien été publiée."),
        **kwargs)


def get_archive_proposal_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("La modération a bien été archivée."),
        **kwargs)


def get_opinion_proposal_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("La proposition a bien été examinée."),
        **kwargs)
    result['counters-to-update'] = [
        'component-navbar-mysupports'
        ]
    return result


def get_publish_proposal_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("La proposition a bien été publiée."),
        **kwargs)


def get_exclude_participant_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("La demande d'exclusion a bien été soumise au groupe de travail."),
        **kwargs)


def get_remove_proposal_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request, context, api,
        _("La proposition a bien été supprimée."),
        **kwargs)
    result['ignore_redirect'] = not kwargs['is_source_context']
    result['counters-to-update'] = [
        'component-navbar-mycontents'
        ]
    return result


def get_participate_proposal_metadata(action, request, context, api, **kwargs):
    user = kwargs['user']
    working_group = getattr(context, 'working_group', None)
    msg = ''
    if user in working_group.wating_list:
        msg = _("Vous êtes maintenant sur la liste d'attente.")

    if user in working_group.members:
        msg = _("Vous êtes maintenant membre du groupe de travail.")

    if user in working_group.wating_list_participation:
        msg = _("Votre demande de participation est maintenant prise en compte.")

    result = get_dirct_edit_entity_metadata(
        action, request, context, api,
        msg,
        **kwargs)
    result['counters-to-update'] = [
        'component-navbar-mycontents',
        'component-navbar-myparticipations'
        ]
    return result


def get_correctitem_proposal_metadata(action, request, context, api, **kwargs):
    user = kwargs['user']
    user_id = get_oid(user)
    inprocess = any('included' not in context.corrections[c] and
                    user_id not in context.corrections[c]['favour']
                    for c in context.corrections.keys())
    result = get_dirct_edit_entity_metadata(
        action, request, context, api,
        _("Votre validation est bien pris en compte"),
        **kwargs)

    if not inprocess:
        object_views_to_update = []
        oid = get_oid(context.proposal, None)
        object_views_to_update = [
            'listing_'+str(oid),
            'index_'+str(oid),
        ]
        kwargs['object_views'].append('listing_'+str(oid))
        result['object_views_to_update'] = object_views_to_update

    return result


def get_resign_proposal_metadata(action, request, context, api, **kwargs):
    result = get_dirct_edit_entity_metadata(
        action, request, context, api,
        _("Vous n'êtes plus maintenant membre du groupe de travail."),
        **kwargs)
    result['counters-to-update'] = [
        'component-navbar-mycontents',
        'component-navbar-myparticipations'
        ]
    source_view_name = kwargs.get('view_name', '')
    view_name = 'seemyparticipations'
    if source_view_name == view_name:
        result['objects_to_hide'] = [
            'listing_'+str(get_oid(context, None))]

    return result


def get_addfiles_proposal_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Les fichiers ont bien été ajoutés dans l'espace de  travail."),
        **kwargs)


def get_removefile_ws_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le fichier à bien été supprimé de l'espace de  travail."),
        **kwargs)
    result['ignore_redirect'] = True
    return result


def get_attachfiles_proposal_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Les fichiers ont bien été attachés à la proposition."),
        **kwargs)

#Organizations

def get_user_edit_organization_metadata(action, request, context, api, **kwargs):
    alert_msg = None
    objects_to_hide = []
    object_views_to_update = []
    redirect_url = None
    body = None
    if 'view_data' in kwargs:
        view_instance, view_result = kwargs['view_data']
        if view_result:
            if isinstance(view_result, HTTPFound) or view_result is nothing:
                alert_msg = _(
                    "Les données associées à l'organisation "
                    "de l'utilisateur ${context} ont bien été"
                    " modifiées.",
                    mapping={
                        'context': getattr(context, 'title', context.__name__)})
                source_context = kwargs.get('source_context', None)
                oid = get_oid(context, None)
                object_views_to_update = [
                    'listing_'+str(oid),
                    'index_'+str(oid),
                ]
                if source_context:
                    if isinstance(source_context, Organization) and\
                       context.organization is not source_context:
                        objects_to_hide = [
                            'listing_'+str(get_oid(context, None))]
                        alert_msg = _(
                            "L'utilisateur ${context} a bien"
                            " changé d'organisation.",
                            mapping={
                                'context': getattr(context, 'title', context.__name__)})

                if isinstance(view_result, HTTPFound):
                    redirect_url = view_result.headers['location']
            else:
                body = view_result['coordinates'][view_instance.coordinates][0]['body']

    result = {
        'action': 'redirect_action',
        'view': api,
        'redirect_url': redirect_url,
        'objects_to_hide': objects_to_hide,
        'view_name': 'index',
        'object_views_to_update': object_views_to_update,
        'new_body': json.dumps(body) if body else None
    }
    result['alert_msg'] = request.localizer.translate(alert_msg) if alert_msg else None
    result['alert_type'] = 'success'
    return result


def get_edit_organization_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Les données de l'organisation"" ont été mis à jour."),
        **kwargs)


def get_remove_organization_metadata(action, request, context, api, **kwargs):
    result = get_edit_entity_metadata(
        action, request, context, api,
        _("L'organisation a bien été supprimée."),
        'seeorganizations', **kwargs)
    user = kwargs.get('user', None)
    registrations = find_entities(
        user=user,
        interfaces=[IOrganization])
    len_result = len(registrations)
    index = str(len_result)
    if len_result > 1:
        index = '*'

    view_title = request.localizer.translate(
        _(ORGANIZATION_CONTENTS_MESSAGES[index],
          mapping={'nember': len_result}))
    result['view_title'] = view_title
    return result


def get_assigne_roles_user_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le rôle de l'utilisateur a bien été modifié."),
        **kwargs)


def get_update_processes_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Les processus sont bien mis à jour."),
        **kwargs)

#Files

def get_publish_file_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le fichier a bien été publié."),
        **kwargs)


def get_private_file_metadata(action, request, context, api, **kwargs):
    return get_edit_entity_metadata(
        action, request,
        context, api,
        _("Le fichier a bien été privatisé."),
        **kwargs)

#Counters

def component_navbar_myselections(action, request, context, api, **kwargs):
    user = kwargs.get('user', None)
    source_view_name = kwargs.get('view_name', '')
    localizer = request.localizer
    selections = [o for o in getattr(user, 'selections', [])
                  if 'archived' not in o.state]
    if getattr(request, 'is_idea_box', False):
        selections = [s for s in selections
                      if not isinstance(s, Proposal)]
    len_selections = len(selections)
    result = {
        'component-navbar-myselections.item_nb': len_selections,
        'component-navbar-myselections.title': localizer.translate(
            _('My following')),
        'component-navbar-myselections.icon': 'glyphicon glyphicon-star-empty',
        'component-navbar-myselections.url': request.resource_url(
            request.root, 'seemyselections'),
    }
    view_name = 'seemyselections'
    if source_view_name == view_name:
        index = str(len_selections)
        if len_selections > 1:
            index = '*'

        view_title = localizer.translate(
                _(SELECT_CONTENTS_MESSAGES[index],
                  mapping={'nember': len_selections}))
        result.update({
            'view_title': view_title,
            'view_name': view_name
        })

    return result


def component_navbar_mysupports(action, request, context, api, **kwargs):
    user = kwargs.get('user', None)
    localizer = request.localizer
    source_view_name = kwargs.get('view_name', '')
    item_nb = len(getattr(user, 'supports', []))
    result = {
        'component-navbar-mysupports.item_nb': item_nb,
        'component-navbar-mysupports.all_item_nb': len(getattr(user, 'tokens_ref', [])),
        'component-navbar-mysupports.title': localizer.translate(_("My supports")),
        'component-navbar-mysupports.icon': 'ion-ios7-circle-filled',
        'component-navbar-mysupports.url': request.resource_url(
            request.root, 'seemysupports')
    }

    view_name = 'seemysupports'
    if source_view_name == view_name:
        len_tokens = len(getattr(user, 'tokens', []))
        index = str(item_nb)
        if item_nb > 1:
            index = '*'

        view_title = localizer.translate(
            _(CONTENTS_MESSAGES[index],
              mapping={'nember': item_nb,
                       'tokens': len_tokens}))
        result.update({
            'view_title': view_title,
            'view_name': view_name
        })

    return result


def component_navbar_mycontents(action, request, context, api, **kwargs):
    user = kwargs.get('user', None)
    localizer = request.localizer
    source_view_name = kwargs.get('view_name', '')
    contents = [o for o in getattr(user, 'contents', [])]
    if getattr(request, 'is_idea_box', False):
        contents = [s for s in contents
                    if not isinstance(s, Proposal)]
    item_nb = len(contents)
    result = {
        'component-navbar-mycontents.item_nb': item_nb,
        'component-navbar-mycontents.title': localizer.translate(_('My contents')),
        'component-navbar-mycontents.icon': 'glyphicon glyphicon-inbox',
        'component-navbar-mycontents.url': request.resource_url(
            request.root, 'seemycontents')
    }

    view_name = 'seemycontents'
    if source_view_name == view_name:
        index = str(item_nb)
        if item_nb > 1:
            index = '*'

        view_title = localizer.translate(
            _(MY_CONTENTS_MESSAGES[index],
              mapping={'nember': item_nb}))
        result.update({
            'view_title': view_title,
            'view_name': view_name
        })

    return result


def novideo_contents_ideas(action, request, context, api, **kwargs):
    dace_catalog = find_catalog('dace')
    states_index = dace_catalog['object_states']
    object_provides_index = dace_catalog['object_provides']
    query = object_provides_index.any((Iidea.__identifier__, )) & \
        states_index.any(['published'])
    item_nb = query.execute().__len__()
    title = _('Published idea')
    if item_nb > 1:
        title = _('Published ideas')

    result = {
        'novideo-contents-ideas.item_nb': item_nb,
        'novideo-contents-ideas.title': request.localizer.translate(title),
    }

    return result


def component_navbar_myparticipations(action, request, context, api, **kwargs):
    user = kwargs.get('user', None)
    localizer = request.localizer
    source_view_name = kwargs.get('view_name', '')
    item_nb = len(getattr(user, 'participations', []))
    result = {
        'component-navbar-myparticipations.item_nb': item_nb,
        'component-navbar-myparticipations.title': request.localizer.translate(_('My working groups')),
        'component-navbar-myparticipations.icon': 'novaideo-icon icon-wg',
        'component-navbar-myparticipations.url': request.resource_url(
            request.root, 'seemyparticipations')
    }

    view_name = 'seemyparticipations'
    if source_view_name == view_name:
        index = str(item_nb)
        if item_nb > 1:
            index = '*'

        view_title = localizer.translate(
            _(MY_PARTICIPATIONS_MESSAGES[index],
              mapping={'nember': item_nb}))
        result.update({
            'view_title': view_title,
            'view_name': view_name
        })

    return result


def person_proposals_counter(action, request, context, api, **kwargs):
    user = kwargs.get('user', None)
    source_context = kwargs.get('source_context', None)
    if source_context is user:
        objects = list(filter(lambda o: 'archived' not in o.state,
                         getattr(user, 'proposals', [])))
    else:
        objects = list(filter(lambda o: can_access(source_context, o) and
                                   'archived' not in o.state,
                         getattr(user, 'proposals', [])))
    title = _('Her working groups (${nb})', mapping={'nb': len(objects)})
    result = {
        'person-proposals-counter.title': request.localizer.translate(title),
    }
    return result


def person_ideas_counter(action, request, context, api, **kwargs):
    user = kwargs.get('user', None)
    source_context = kwargs.get('source_context', None)
    if source_context is user:
        objects = list(filter(lambda o: 'archived' not in o.state,
                              getattr(user, 'ideas', [])))
    else:
        objects = list(filter(lambda o: can_access(source_context, o) and
                                        'archived' not in o.state,
                              getattr(user, 'ideas', [])))
    title = _('Her ideas (${nb})', mapping={'nb': len(objects)})
    result = {
        'person-ideas-counter.title': request.localizer.translate(title),
        }
    return result


def home_proposals_counter(action, request, context, api, **kwargs):
    #TODO
    return {}


def home_ideas_counter(action, request, context, api, **kwargs):
    dace_catalog = find_catalog('dace')
    states_index = dace_catalog['object_states']
    object_provides_index = dace_catalog['object_provides']
    query = object_provides_index.any((Iidea.__identifier__, )) & \
        states_index.any(['published'])
    item_nb = query.execute().__len__()
    title = _('Ideas (${nb})', mapping={'nb': item_nb})

    result = {
        'home-ideas-counter.title': request.localizer.translate(title),
    }
    return result


METADATA_GETTERS = {
    'smartfoldermanagement.edit_smart_folder': get_edit_folder_metadata,
    'smartfoldermanagement.remove_smart_folder': get_remove_folder_metadata,
    'smartfoldermanagement.publish_smart_folder': get_publish_folder_metadata,
    'smartfoldermanagement.withdraw_smart_folder': get_archive_folder_metadata,
    'smartfoldermanagement.addsub_smart_folder': get_add_subfolder_metadata,

    'novaideoabstractprocess.select': get_selection_metadata,
    'novaideoabstractprocess.deselect': get_selection_metadata,
    'novaideoprocessmanagement.update': get_update_processes_metadata,

    'reportsmanagement.report': get_report_entity_metadata,
    'reportsmanagement.censor': get_censor_entity_metadata,
    'reportsmanagement.ignore': get_ignore_entity_metadata,
    'reportsmanagement.restor': get_restor_entity_metadata,

    'novaideoviewmanager.contact': get_default_action_metadata,

    'newslettermanagement.subscribe': get_default_action_metadata,

    'channelmanagement.subscribe': get_subscribtion_metadata,
    'channelmanagement.unsubscribe': get_subscribtion_metadata,

    'ideamanagement.creat': get_create_idea_metadata,
    'ideamanagement.creatandpublish': get_create_idea_metadata,
    'ideamanagement.creatandpublishasproposal': get_create_idea_metadata,
    'ideamanagement.delidea': get_remove_idea_metadata,
    'ideamanagement.duplicate': get_default_action_metadata,
    'ideamanagement.edit': get_edit_idea_metadata,
    'ideamanagement.archive': get_archive_idea_metadata,
    'ideamanagement.submit': get_submit_idea_metadata,
    'ideamanagement.abandon': get_dirct_archive_idea_metadata,
    'ideamanagement.recuperate': get_dirct_recuperate_idea_metadata,
    'ideamanagement.publish': get_publish_idea_metadata,
    'ideamanagement.makeitsopinion': get_opinion_idea_metadata,
    'ideamanagement.support': get_support_metadata,
    'ideamanagement.oppose': get_support_metadata,
    'ideamanagement.withdraw_token': get_support_metadata,
    'ideamanagement.comment': get_comment_metadata,
    'ideamanagement.present': get_present_metadata,

    'proposalmanagement.submit': get_submit_proposal_metadata,
    'proposalmanagement.support': get_support_metadata,
    'proposalmanagement.oppose': get_support_metadata,
    'proposalmanagement.withdraw_token': get_support_metadata,
    'proposalmanagement.comment': get_comment_metadata,
    'proposalmanagement.present': get_present_metadata,
    'proposalmanagement.makeitsopinion': get_opinion_proposal_metadata,
    'proposalmanagement.delete': get_remove_proposal_metadata,
    'proposalmanagement.attach_files': get_attachfiles_proposal_metadata,
    'proposalmanagement.publish': get_publish_proposal_metadata,
    'proposalmanagement.exclude_participant': get_exclude_participant_metadata,
    'proposalmanagement.resign': get_resign_proposal_metadata,
    'proposalmanagement.participate': get_participate_proposal_metadata,
    'workspacemanagement.add_files': get_addfiles_proposal_metadata,
    'workspacemanagement.remove_file': get_removefile_ws_metadata,
    'correctionworkmodeprocess.correctitem': get_correctitem_proposal_metadata,

    'amendmentmanagement.comment': get_comment_metadata,
    'amendmentmanagement.present': get_present_metadata,

    'usermanagement.discuss': get_discuss_metadata,
    'usermanagement.general_discuss': get_general_discuss_metadata,
    'usermanagement.assign_roles': get_assigne_roles_user_metadata,
    'usermanagement.deactivate': get_deactivate_profile_metadata,

    'commentmanagement.pin': get_comment_pin_metadata,
    'commentmanagement.unpin': get_comment_unpin_metadata,
    'commentmanagement.respond': get_respond_metadata,
    'commentmanagement.remove': get_remove_comment_metadata,
    'commentmanagement.edit': get_edit_comment_metadata,
    'commentmanagement.transformtoidea': get_tranform_into_idea_metadata,

    'registrationmanagement.remove': get_remove_registration_metadata,
    'registrationmanagement.remind': get_remind_registration_metadata,

    'invitationmanagement.edit': get_edit_invitation_metadata,
    'invitationmanagement.remove': get_remove_invitation_metadata,
    'invitationmanagement.reinvite': get_remind_invitation_metadata,
    'invitationmanagement.remind': get_remind_invitation_metadata,
    'invitationmanagement.refuse': get_refuse_invitation_metadata,

    'organizationmanagement.edit': get_edit_organization_metadata,
    'organizationmanagement.remove': get_remove_organization_metadata,
    'organizationmanagement.withdraw_user': get_withdraw_user_metadata,
    'organizationmanagement.add_members': get_edit_organization_metadata,
    'organizationmanagement.remove_members': get_edit_organization_metadata,
    'organizationmanagement.user_edit_organization': get_user_edit_organization_metadata,

    'novaideofilemanagement.publish': get_publish_file_metadata,
    'novaideofilemanagement.private': get_private_file_metadata
}


COUNTERS_COMPONENTS = {
   'component-navbar-mycontents': component_navbar_mycontents,
   'component-navbar-myparticipations': component_navbar_myparticipations,
   'component-navbar-myselections': component_navbar_myselections,
   'component-navbar-mysupports': component_navbar_mysupports,
   'person-proposals-counter': person_proposals_counter,
   'person-ideas-counter': person_ideas_counter,
   'home-proposals-counter': home_proposals_counter,
   'home-ideas-counter': home_ideas_counter,
   'novideo-contents-ideas': novideo_contents_ideas
}
