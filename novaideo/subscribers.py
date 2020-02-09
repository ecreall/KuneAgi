# Copyright (c) 2014 by Ecreall under licence AGPL terms
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import os
import transaction
from ZODB.POSException import ConflictError
from persistent.list import PersistentList

from pyramid.events import subscriber, ApplicationCreated
from pyramid.threadlocal import get_current_registry, get_current_request
from pyramid.request import Request
from pyramid.threadlocal import manager
from pyramid.interfaces import IRequest

from pyramid_sms.ovh import OvhService
from pyramid_sms.interfaces import ISMSService
from substanced.event import RootAdded
from substanced.util import find_service, get_oid

from dace.util import getSite, find_catalog
from pontus.file import File

from novaideo import core
from novaideo.event import (
    ObjectPublished, CorrelableRemoved,
    ObjectModified)
from novaideo.views.filter import (
    get_users_by_keywords, get_users_by_preferences)
from novaideo.content.processes import get_states_mapping
from novaideo import _, add_nia_bot
from novaideo.content.alert import InternalAlertKind
from novaideo.content.invitation import Invitation
from novaideo.role import APPLICATION_ROLES
from novaideo.utilities.alerts_utility import (
    alert, get_user_data, get_entity_data)
from novaideo.utilities.util import gen_random_token
from novaideo.mail.fr import FIRST_INVITATION, FIRST_INVITATION_SMS


_CONTENT_TRANSLATION = [_("The proposal"),
                        _("The idea")]


def ideation_conf(root):
    root.content_to_manage = PersistentList(['question'])
    root.content_to_support = PersistentList(['idea'])
    root.content_to_examine = PersistentList(['idea'])


def cocreation_conf(root):
    root.content_to_manage = PersistentList(['question', 'proposal'])
    root.content_to_support = PersistentList(['idea', 'proposal'])
    root.content_to_examine = PersistentList(['proposal'])


def coresolution_conf(root):
    root.content_to_manage = PersistentList(
        ['challenge', 'question', 'proposal'])
    root.content_to_support = PersistentList(['idea', 'proposal'])
    root.content_to_examine = PersistentList(['proposal'])


CONFIGURATIONS = {
    'ideation': ideation_conf,
    'cocreation': cocreation_conf,
    'coresolution': coresolution_conf,
}


def _invite_first_user(root, request, title, first_name, last_name, email, phone):
    registry = request.registry
    first_user_roles = ['SiteAdmin']
    settings = registry.settings
    application_url = settings.get('application.url')
    principals = find_service(root, 'principals')
    user = principals['users']['admin']
    invitation = Invitation(
        user_title=title,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        roles=first_user_roles,
    )
    mail_template = root.get_mail_template('invitation')
    novaideo_title = root.title
    invitation.state.append('pending')
    invitation.setproperty('manager', user)
    invitation.__name__ = gen_random_token()
    root.addtoproperty('invitations', invitation)
    invitation.reindex()
    roles_translate = [APPLICATION_ROLES.get(r, r)
                       for r in invitation.roles]
    url = application_url + '/' + invitation.__name__
    if email:
        # send email
        subject = FIRST_INVITATION['subject'].format(
            novaideo_title=novaideo_title
        )
        message = FIRST_INVITATION['template'].format(
            recipient_title='',
            recipient_first_name=invitation.first_name,
            recipient_last_name=invitation.last_name,
            invitation_url=url,
            roles=", ".join(roles_translate),
            novaideo_title=novaideo_title)
        alert('email', [root.get_site_sender()], [invitation.email],
              subject=subject, body=message)

    if phone:
        # send sms
        message = FIRST_INVITATION_SMS['template'].format(
            recipient_title='',
            recipient_first_name=invitation.first_name,
            recipient_last_name=invitation.last_name,
            invitation_url=url,
            roles=", ".join(roles_translate),
            novaideo_title=novaideo_title)
        alert('sms', recipients=[phone],
              request=request, message=message)


@subscriber(RootAdded)
def mysubscriber(event):
    """Add the novaideo conf when the root is added."""
    root = event.object
    registry = get_current_registry()
    settings = registry.settings
    novaideo_title = settings.get('novaideo.title')
    root.title = novaideo_title
    root.init_files()
    root.init_channels()
    catalogs = find_service(root, 'catalogs')
    catalogs.add_catalog('novaideo')
    site_type = os.getenv('INITIAL_SITE_TYPE', 'public')
    root.only_for_members = site_type.lower() != 'public'
    site_conf = CONFIGURATIONS.get(
        os.getenv('INITIAL_SITE_CONF', 'ideation'), ideation_conf)
    site_conf(root)
    # invit initial user
    root.first_invitation_to_add = True
    root.locale = settings.get('pyramid.default_locale_name')
    add_nia_bot(root)


@subscriber(ObjectPublished)
def mysubscriber_object_published(event):
    content = event.object
    author = getattr(content, 'author', None)
    tree = content.tree
    request = get_current_request()
    root = request.root
    challenge = getattr(content, 'challenge', None)
    query = None
    challeng_followers = []
    if getattr(challenge, 'is_restricted', False):
        novaideo_catalog = find_catalog('novaideo')
        challenges_index = novaideo_catalog['challenges']
        query = challenges_index.any([get_oid(challenge)])
    elif challenge:
        challeng_followers = get_users_by_preferences(challenge)
        alert('internal', [root], set(challeng_followers),
              internal_kind=InternalAlertKind.content_alert,
              subjects=[content], alert_kind='published_in_challenge')

    users = get_users_by_keywords(tree, query)
    subject_data = get_entity_data(content, 'subject', request)
    all_users = []
    for member in users:
        all_users.append(member)
        if getattr(member, 'email', '') and author is not member:
            mail_template = root.get_mail_template(
                'alert_new_content', member.user_locale)
            subject = mail_template['subject'].format(
                **subject_data)
            email_data = get_user_data(member, 'recipient', request)
            email_data.update(subject_data)
            message = mail_template['template'].format(
                novaideo_title=root.title,
                **email_data
            )
            alert('email', [root.get_site_sender()], [member.email],
                  subject=subject, body=message)

    if author in all_users:
        all_users.remove(author)

    alert('internal', [root], set(all_users),
          internal_kind=InternalAlertKind.content_alert,
          subjects=[content], alert_kind='published')

    pref_author = get_users_by_preferences(author)
    all_users = [u for u in pref_author if u not in set(all_users)]
    alert('internal', [root], all_users,
          internal_kind=InternalAlertKind.content_alert,
          subjects=[content], alert_kind='published_author',
          member_url=request.resource_url(author, '@@index'),
          member_title=getattr(author, 'title', author.__name__))

    if getattr(content, 'original', None):
        original = content.original
        users = list(get_users_by_preferences(original))
        users.append(original.author)
        alert('internal', [root], set(users),
              internal_kind=InternalAlertKind.content_alert,
              subjects=[content], alert_kind='duplicated',
              url=request.resource_url(original, '@@index'),
              duplicate_title=original.title)


@subscriber(ObjectModified)
def mysubscriber_object_modified(event):
    content = event.object
    args = event.args
    state_source = args.get('state_source', '')
    state_target = args.get('state_target', '')
    request = get_current_request()
    users = get_users_by_preferences(content)
    root = request.root
    localizer = request.localizer
    subject_data = get_entity_data(content, 'subject', request)
    all_users = []
    for member in users:
        all_users.append(member)
        if getattr(member, 'email', ''):
            mail_template = root.get_mail_template(
                'alert_content_modified', member.user_locale)
            subject = mail_template['subject'].format(
                **subject_data)
            state_source_translate = state_source
            state_target_translate = state_target
            if state_source:
                state_source_translate = localizer.translate(
                    get_states_mapping(
                        member, content, state_source))
            if state_target:
                state_target_translate = localizer.translate(
                    get_states_mapping(
                        member, content, state_target))

            email_data = get_user_data(member, 'recipient', request)
            email_data.update(subject_data)
            message = mail_template['template'].format(
                state_source=state_source_translate,
                state_target=state_target_translate,
                novaideo_title=root.title,
                **email_data
            )
            alert('email', [root.get_site_sender()], [member.email],
                  subject=subject, body=message)

    alert('internal', [root], all_users,
          internal_kind=InternalAlertKind.content_alert,
          subjects=[content], alert_kind='modified')


@subscriber(CorrelableRemoved)
def mysubscriber_correlable_removed(event):
    root = getSite()
    removed_object = event.object
    # get all versions. Versions will be removed
    all_versions = getattr(removed_object, 'history', [])
    if removed_object in all_versions:
        all_versions.remove(removed_object)

    # recuperate all correlations
    source_correlations = removed_object.source_correlations
    [source_correlations.extend(getattr(version, 'source_correlations', []))
     for version in all_versions]
    # destroy all versions
    if hasattr(removed_object, 'destroy'):
        removed_object.destroy()

    # update correlations
    for correlation in source_correlations:
        for target in list(correlation.targets):
            correlation.delfromproperty('targets', target)

        root.delfromproperty('correlations', correlation)


@subscriber(ApplicationCreated)
def init_application(event):
    app = event.object
    registry = app.registry
    request = Request.blank('/application_created')  # path is meaningless
    request.registry = registry
    manager.push({'registry': registry, 'request': request})
    # Set up sms service backend
    registry.registerAdapter(
        factory=OvhService,
        required=(IRequest,),
        provided=ISMSService)
    root = app.root_factory(request)
    # A transaction.commit() just happened here if this is the first time we
    # start. This is just after all RootAdded subscribers are executed.
    request.root = root
    # other init functions
    if getattr(root, 'locale', None) is None:
        try:
            # This code is actually an evolve step for old novaideo instances.
            # The root.locale is set in the RootAdded subscriber above
            # for new instances.
            root.locale = registry.settings.get('pyramid.default_locale_name')
            transaction.commit()
        except ConflictError:
            # We have a conflict error in case of serveral workers, just abort
            transaction.abort()

    init_contents(registry)  # there is no changes in ZODB here
    # invite initial user if first deployment
    if getattr(root, 'first_invitation_to_add', False):
        # LOGO_FILENAME='marianne.svg' for example
        logo = os.getenv('LOGO_FILENAME', '')
        if logo:
            logo_path = os.path.join(
                os.path.dirname(__file__), 'static', 'images', logo)
            if os.path.exists(logo_path):
                buf = open(logo_path, mode='rb')
                log_file = File(
                    fp=buf, filename=logo, mimetype='image/svg+xml')
                root.setproperty('picture', log_file)

        title = os.getenv('INITIAL_USER_TITLE', '')
        first_name = os.getenv('INITIAL_USER_FIRSTNAME', '')
        last_name = os.getenv('INITIAL_USER_LASTNAME', '')
        email = os.getenv('INITIAL_USER_EMAIL', '')
        phone = os.getenv('INITIAL_USER_PHONE', '')
        if first_name and last_name and (phone or email):
            _invite_first_user(
                root, request, title,
                first_name, last_name, email, phone)

        del root.first_invitation_to_add
        # This is a change in ZODB, but it's ok, it is executed only the first
        # time when we only have one worker.

    transaction.commit()
    manager.pop()


def init_contents(registry):
    """Init searchable content"""
    core.SEARCHABLE_CONTENTS = {
        type_id: c
        for type_id, c in registry.content.content_types.items()
        if core.SearchableEntity in c.mro()
    }

    core.SUSTAINABLE_CONTENTS = {
        type_id: c
        for type_id, c in registry.content.content_types.items()
        if core.Sustainable in c.mro()
    }
