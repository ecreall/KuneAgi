# Copyright (c) 2014 by Ecreall under licence AGPL terms
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import datetime
import pytz
from pyramid.httpexceptions import HTTPFound
from substanced.util import find_service

from dace.util import getSite, name_chooser, find_catalog
from dace.objectofcollaboration.principal.util import (
    grant_roles, has_role, get_current, has_any_roles)
from dace.processinstance.activity import (
    InfiniteCardinality,
    ActionType)
from pontus.schema import select, omit

from novaideo.ips.xlreader import get_data_from_xl
from novaideo.content.interface import (
    INovaIdeoApplication, IInvitation, IOrganization)
from novaideo.content.invitation import Invitation
from novaideo import _, nothing, my_locale_negotiator
from novaideo.content.processes.user_management.behaviors import (
    global_user_processsecurity)
from novaideo.core import access_action, serialize_roles
from novaideo.utilities.util import gen_random_token
from novaideo.content.person import Person
from novaideo.content.invitation import InvitationSchema
from novaideo.role import DEFAULT_ROLES, APPLICATION_ROLES
from novaideo.utilities.alerts_utility import (
    alert, get_user_data, get_entity_data)
from novaideo.views.filter import get_entities_by_title


INVITATION_ROLES = {
    'moderator': 'Moderator',
    'member': 'Member',
    'examiner': 'Examiner'
}


def uploaduser_roles_validation(process, context):
    return has_role(role=('Moderator',))


def uploaduser_processsecurity_validation(process, context):
    return global_user_processsecurity()


class UploadUsers(InfiniteCardinality):
    style = 'button'  # TODO add style abstract class
    style_descriminator = 'admin-action'
    style_picto = 'glyphicon glyphicon-bullhorn'
    style_order = 5.2
    submission_title = _('Import')
    isSequential = False
    context = INovaIdeoApplication
    roles_validation = uploaduser_roles_validation
    processsecurity_validation = uploaduser_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        user = get_current()
        novaideo_catalog = find_catalog('novaideo')
        identifier_index = novaideo_catalog['identifier']
        user_titles = {str(i).lower(): str(i) for i in root.titles}
        title_template = u"""{title} {first_name} {last_name}"""
        mail_template = root.get_mail_template('invitation')
        localizer = request.localizer
        novaideo_title = root.title
        xlfile = appstruct['file']['_object_data']
        invitations_data = get_data_from_xl(
            file=xlfile,
            properties={'first_name': ('String', False),
                        'last_name': ('String', False),
                        'user_title': ('String', False),
                        'email': ('String', False),
                        'organization': ('String', False),
                        'ismanager': ('Boolean', False),
                        'roles': ('String', True)})
        for invitation_data in invitations_data:
            email = invitation_data['email']
            if email and invitation_data['first_name'] and invitation_data['last_name']:
                query = identifier_index.any([email])
                users = list(query.execute().all())
                if not users:
                    organization_title = invitation_data.pop(
                        'organization', None)
                    organizations = list(get_entities_by_title(
                        [IOrganization], organization_title).all())
                    organization = organizations[0] if organizations else None

                    roles = invitation_data.get('roles', [])
                    roles = [INVITATION_ROLES.get(r.lower()) for
                             r in roles if r.lower() in INVITATION_ROLES]
                    roles = roles or ['Member']
                    invitation_data['roles'] = roles

                    user_title = invitation_data['user_title']
                    invitation_data['user_title'] = user_titles.get(
                        user_title.lower(), 'Mr') if user_title else 'Mr'

                    invitation_data['title'] = title_template.format(
                        title=invitation_data['user_title'],
                        first_name=invitation_data['first_name'],
                        last_name=invitation_data['last_name'])
                    invitation = Invitation(**invitation_data)
                    invitation.state.append('pending')
                    invitation.setproperty('manager', user)
                    invitation.__name__ = gen_random_token()
                    if organization:
                        invitation.setproperty('organization', organization)

                    root.addtoproperty('invitations', invitation)
                    roles_translate = [localizer.translate(APPLICATION_ROLES.get(r, r))
                                       for r in getattr(invitation, 'roles', [])]

                    subject = mail_template['subject'].format(
                        novaideo_title=novaideo_title
                    )
                    email_data = get_user_data(
                        invitation, 'recipient', request)
                    email_data.update(get_entity_data(
                        invitation, 'invitation', request))
                    message = mail_template['template'].format(
                        roles=", ".join(roles_translate),
                        novaideo_title=novaideo_title,
                        **email_data)
                    alert('email', [root.get_site_sender()], [invitation.email],
                          subject=subject, body=message)

        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(request.root, '@@seeinvitations'))


def inviteuser_roles_validation(process, context):
    return has_role(role=('Moderator',)) or \
        has_role(role=('OrganizationResponsible',))


def inviteuser_processsecurity_validation(process, context):
    return global_user_processsecurity()


class InviteUsers(InfiniteCardinality):
    style_descriminator = 'admin-action'
    style_picto = 'glyphicon glyphicon-bullhorn'
    style_order = 5.2
    submission_title = _('Send')
    isSequential = False
    context = INovaIdeoApplication
    roles_validation = inviteuser_roles_validation
    processsecurity_validation = inviteuser_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        invitations = appstruct['invitations']
        user = get_current()
        mail_template = root.get_mail_template('invitation')
        localizer = request.localizer
        novaideo_title = root.title
        for invitation_dict in invitations:
            invitation = invitation_dict['_object_data']
            invitation.state.append('pending')
            invitation.setproperty('manager', user)
            invitation.__name__ = gen_random_token()
            root.addtoproperty('invitations', invitation)
            if not getattr(invitation, 'roles', []):
                invitation.roles = DEFAULT_ROLES

            roles_translate = [localizer.translate(APPLICATION_ROLES.get(r, r))
                               for r in invitation.roles]
            subject = mail_template['subject'].format(
                novaideo_title=novaideo_title
            )
            email_data = get_user_data(invitation, 'recipient', request)
            email_data.update(get_entity_data(
                invitation, 'invitation', request))
            message = mail_template['template'].format(
                roles=", ".join(roles_translate),
                novaideo_title=novaideo_title,
                **email_data)
            alert('email', [root.get_site_sender()], [invitation.email],
                  subject=subject, body=message)

        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, '@@seeinvitations'))


def get_access_key(obj):
    organization = obj.organization
    result = []
    if organization:
        result = serialize_roles(
            (('OrganizationResponsible', organization),))

    result.extend(serialize_roles(
        ('Moderator', 'Anonymous')))
    return result


def seeinv_processsecurity_validation(process, context):
    organization = context.organization
    return (organization and
            has_role(role=('OrganizationResponsible',
                           organization))) or \
        has_any_roles(roles=('Moderator',
                             'Anonymous'))


@access_action(access_key=get_access_key)
class SeeInvitation(InfiniteCardinality):
    isSequential = False
    title = _('More')
    actionType = ActionType.automatic
    context = IInvitation
    processsecurity_validation = seeinv_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context))


def seeinvs_roles_validation(process, context):
    return has_any_roles(roles=('Moderator', 'OrganizationResponsible'))


def seeinvs_processsecurity_validation(process, context):
    return global_user_processsecurity()


class SeeInvitations(InfiniteCardinality):
    style_descriminator = 'admin-action'
    style_picto = 'glyphicon glyphicon-bullhorn'
    style_order = 10
    isSequential = False
    context = INovaIdeoApplication
    roles_validation = seeinvs_roles_validation
    processsecurity_validation = seeinvs_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context))


def edit_roles_validation(process, context):
    return has_role(role=('SiteAdmin',))


def edit_processsecurity_validation(process, context):
    return global_user_processsecurity() and \
        context.invitations


class EditInvitations(InfiniteCardinality):
    style_descriminator = 'admin-action'
    style_picto = 'glyphicon glyphicon-bullhorn'
    style_order = 7
    submission_title = _('Save')
    isSequential = False
    context = INovaIdeoApplication
    roles_validation = edit_roles_validation
    processsecurity_validation = edit_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        return {}

    def redirect(self, context, request, **kw):
        return HTTPFound(request.resource_url(context, '@@seeinvitations'))


def editinv_roles_validation(process, context):
    return (context.organization and
            has_role(role=('OrganizationResponsible',
                           context.organization))) or \
        has_role(role=('Moderator',))


def editinv_processsecurity_validation(process, context):
    return global_user_processsecurity()


class EditInvitation(InfiniteCardinality):
    style = 'button'  # TODO add style abstract class
    style_descriminator = 'primary-action'
    style_interaction = 'ajax-action'
    style_picto = 'glyphicon glyphicon-pencil'
    isSequential = False
    title = _('Edit the invitation')
    submission_title = _('Save')
    context = IInvitation
    roles_validation = editinv_roles_validation
    processsecurity_validation = editinv_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        context.modified_at = datetime.datetime.now(tz=pytz.UTC)
        context.reindex()
        return {}

    def redirect(self, context, request, **kw):
        return nothing


def accept_roles_validation(process, context):
    return has_role(role=('Anonymous',)) and \
        not has_role(role=('SiteAdmin',))


def accept_state_validation(process, context):
    return 'pending' in context.state


class AcceptInvitation(InfiniteCardinality):
    style = 'button'  # TODO add style abstract class
    style_descriminator = 'primary-action'
    style_interaction = 'ajax-action'
    context = IInvitation
    style_picto = 'glyphicon glyphicon-ok'
    submission_title = _('Save')
    roles_validation = accept_roles_validation
    state_validation = accept_state_validation

    def start(self, context, request, appstruct, **kw):
        datas = context.get_data(select(omit(InvitationSchema(),
                                             ['_csrf_token_']),
                                        ['user_title',
                                         'roles',
                                         'first_name',
                                         'last_name',
                                         'birth_date',
                                         'birthplace',
                                         'citizenship',
                                         'email',
                                         'organization']))
        datas['pseudonym'] = appstruct.get('pseudonym', None)
        roles = datas.pop('roles')
        password = appstruct['password']
        datas['locale'] = my_locale_negotiator(request)
        person = Person(password=password, **datas)
        root = getSite(context)
        principals = find_service(root, 'principals')
        users = principals['users']
        name = person.first_name + ' ' + person.last_name \
            if not datas['pseudonym'] else \
            person.pseudonym
        name = name_chooser(users, name=name)
        users[name] = person
        if getattr(context, 'ismanager', False) and \
           context.organization:
            grant_roles(person, (('OrganizationResponsible',
                                  context.organization),))

        person.state.append('active')
        grant_roles(person, roles)
        grant_roles(person, (('Owner', person),))
        manager = context.manager
        root.delfromproperty('invitations', context)
        root.addtoproperty('news_letter_members', person)
        newsletters = root.get_newsletters_automatic_registration()
        email = getattr(person, 'email', '')
        if newsletters and email:
            for newsletter in newsletters:
                newsletter.subscribe(
                    person.first_name, person.last_name, email)

        context.person = person
        if manager:
            mail_template = root.get_mail_template(
                'accept_invitation',
                getattr(manager, 'user_locale', root.locale))
            localizer = request.localizer
            email_data = get_user_data(person, 'user', request, True)
            novaideo_title = request.root.title
            roles_translate = [localizer.translate(APPLICATION_ROLES.get(r, r))
                               for r in roles]
            subject = mail_template['subject'].format(
                novaideo_title=novaideo_title,
                **email_data
            )
            email_data.update(get_user_data(manager, 'recipient', request))
            email_data.update(get_entity_data(person, 'user', request))
            message = mail_template['template'].format(
                roles=", ".join(roles_translate),
                novaideo_title=novaideo_title,
                **email_data)
            alert('email', [root.get_site_sender()], [manager.email],
                  subject=subject, body=message)

        return {}

    def redirect(self, context, request, **kw):
        return nothing


def refuse_roles_validation(process, context):
    return has_role(role=('Anonymous',)) and \
        not has_role(role=('SiteAdmin',))


def refuse_state_validation(process, context):
    return 'pending' in context.state


class RefuseInvitation(InfiniteCardinality):
    style = 'button'  # TODO add style abstract class
    style_descriminator = 'primary-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'direct'
    style_picto = 'glyphicon glyphicon-remove'
    context = IInvitation
    roles_validation = refuse_roles_validation
    state_validation = refuse_state_validation

    def start(self, context, request, appstruct, **kw):
        context.state.remove('pending')
        context.state.append('refused')
        context.modified_at = datetime.datetime.now(tz=pytz.UTC)
        context.reindex()
        manager = context.manager
        if manager:
            root = getSite()
            mail_template = root.get_mail_template(
                'refuse_invitation',
                getattr(manager, 'user_locale', root.locale))
            localizer = request.localizer
            email_data = get_user_data(context, 'user', request)
            novaideo_title = request.root.title
            roles_translate = [localizer.translate(APPLICATION_ROLES.get(r, r))
                               for r in context.roles]
            subject = mail_template['subject'].format(
                novaideo_title=novaideo_title,
                **email_data
            )
            email_data.update(get_user_data(manager, 'recipient', request))
            email_data.update(get_entity_data(context, 'invitation', request))
            message = mail_template['template'].format(
                roles=", ".join(roles_translate),
                novaideo_title=novaideo_title,
                **email_data)
            alert('email', [root.get_site_sender()], [manager.email],
                  subject=subject, body=message)

        return {}

    def redirect(self, context, request, **kw):
        return nothing


def remove_roles_validation(process, context):
    return (context.organization and
            has_role(role=('OrganizationResponsible',
                           context.organization))) or \
        has_role(role=('Moderator',))


def remove_processsecurity_validation(process, context):
    return global_user_processsecurity()


class RemoveInvitation(InfiniteCardinality):
    style = 'button'  # TODO add style abstract class
    style_descriminator = 'primary-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'direct'
    style_picto = 'glyphicon glyphicon-trash'
    context = IInvitation
    roles_validation = remove_roles_validation
    processsecurity_validation = remove_processsecurity_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        root.delfromproperty('invitations', context)
        return {}

    def redirect(self, context, request, **kw):
        root = getSite()
        return HTTPFound(request.resource_url(root, '@@seeinvitations'))


def reinvite_roles_validation(process, context):
    return (context.organization and
            has_role(role=('OrganizationResponsible',
                           context.organization))) or \
        has_role(role=('Moderator',))


def reinvite_processsecurity_validation(process, context):
    return global_user_processsecurity()


def reinvite_state_validation(process, context):
    return 'refused' in context.state


class ReinviteUser(InfiniteCardinality):
    style = 'button'  # TODO add style abstract class
    style_descriminator = 'primary-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'direct'
    style_picto = 'glyphicon glyphicon-bullhorn'
    context = IInvitation
    roles_validation = reinvite_roles_validation
    processsecurity_validation = reinvite_processsecurity_validation
    state_validation = reinvite_state_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        mail_template = root.get_mail_template('invitation')
        localizer = request.localizer
        roles_translate = [localizer.translate(APPLICATION_ROLES.get(r, r))
                           for r in getattr(context, 'roles', [])]
        subject = mail_template['subject'].format(
            novaideo_title=root.title
        )
        email_data = get_user_data(context, 'recipient', request)
        email_data.update(get_entity_data(context, 'invitation', request))
        message = mail_template['template'].format(
            roles=", ".join(roles_translate),
            novaideo_title=root.title,
            **email_data)
        alert('email', [root.get_site_sender()], [context.email],
              subject=subject, body=message)
        context.state.remove('refused')
        context.state.append('pending')
        return {}

    def redirect(self, context, request, **kw):
        return nothing


def remind_roles_validation(process, context):
    return (context.organization and
            has_role(role=('OrganizationResponsible',
                           context.organization))) or \
        has_role(role=('Moderator',))


def remind_processsecurity_validation(process, context):
    return global_user_processsecurity()


def remind_state_validation(process, context):
    return 'pending' in context.state


class RemindInvitation(InfiniteCardinality):
    style = 'button'  # TODO add style abstract class
    style_descriminator = 'primary-action'
    style_interaction = 'ajax-action'
    style_interaction_type = 'direct'
    style_picto = 'glyphicon glyphicon-bullhorn'
    isSequential = True
    context = IInvitation
    roles_validation = remind_roles_validation
    processsecurity_validation = remind_processsecurity_validation
    state_validation = remind_state_validation

    def start(self, context, request, appstruct, **kw):
        root = getSite()
        mail_template = root.get_mail_template('invitation')
        localizer = request.localizer
        roles_translate = [localizer.translate(APPLICATION_ROLES.get(r, r))
                           for r in getattr(context, 'roles', [])]
        subject = mail_template['subject'].format(
            novaideo_title=root.title
        )
        email_data = get_user_data(context, 'recipient', request)
        email_data.update(get_entity_data(context, 'invitation', request))
        message = mail_template['template'].format(
            roles=", ".join(roles_translate),
            novaideo_title=root.title,
            **email_data)
        alert('email', [root.get_site_sender()], [context.email],
              subject=subject, body=message)
        return {}

    def redirect(self, context, request, **kw):
        return nothing

# TODO behaviors
