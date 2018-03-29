# Copyright (c) 2014 by Ecreall under licence AGPL terms
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import colander
import deform
from zope.interface import invariant

from pontus.schema import omit, select, Schema
from pontus.widget import (
    SequenceWidget, SimpleMappingWidget,
    CheckboxChoiceWidget, Select2Widget,
    RichTextWidget)
from pontus.file import ObjectData, File
from deform_treepy.widget import (
    DictSchemaType, KeywordsTreeWidget)
from deform_treepy.utilities.tree_utility import (
    tree_min_len)

from novaideo.content.processes.proposal_management import WORK_MODES
from novaideo import _, AVAILABLE_LANGUAGES, DEFAULT_CONTENT_TO_MANAGE, DEFAULT_EVENTS_DESCRIPTIONS
from novaideo.mail import DEFAULT_SITE_MAILS
from novaideo.core_schema import ContactSchema
from novaideo import core
from novaideo.content import get_file_widget
from novaideo.content.keyword import (
    DEFAULT_TREE, DEFAULT_TREE_LEN)
from .person import locale_widget, locale_missing


@colander.deferred
def modes_choice(node, kw):
    request = node.bindings['request']
    localizer = request.localizer
    modes = list(WORK_MODES.items())
    modes = sorted(modes, key=lambda e: e[1].order)
    values = [(key, localizer.translate(value.title)) for key, value in modes]
    return CheckboxChoiceWidget(values=values, multiple=True)


@colander.deferred
def content_types_choices(node, kw):
    content_to_examine = ['idea', 'proposal']
    request = node.bindings['request']
    localizer = request.localizer
    values = [(key, localizer.translate(
              getattr(c, 'type_title', c.__class__.__name__)))
              for key, c in list(core.SEARCHABLE_CONTENTS.items())
              if key in content_to_examine]
    return CheckboxChoiceWidget(values=sorted(values), multiple=True)


@colander.deferred
def content_manage_choices(node, kw):
    content_to_manage = DEFAULT_CONTENT_TO_MANAGE
    request = node.bindings['request']
    localizer = request.localizer
    values = [(key, localizer.translate(
              getattr(c, 'type_title', c.__class__.__name__)))
              for key, c in list(core.SEARCHABLE_CONTENTS.items())
              if key in content_to_manage]
    return CheckboxChoiceWidget(values=sorted(values), multiple=True)


class WorkParamsConfigurationSchema(Schema):
    """Schema for site configuration."""

    content_to_manage = colander.SchemaNode(
        colander.Set(),
        widget=content_manage_choices,
        title=_('Contents to be managed with the ideas'),
        description=_('Content that can be created by members. Ideas are included by default.'),
        default=DEFAULT_CONTENT_TO_MANAGE,
        missing=DEFAULT_CONTENT_TO_MANAGE
    )

    content_to_moderate = colander.SchemaNode(
        colander.Set(),
        widget=content_types_choices,
        title=_('Contents to be moderated'),
        description=_('Contents can be moderated.'),
        missing=[]
    )

    content_to_support = colander.SchemaNode(
        colander.Set(),
        widget=content_types_choices,
        title=_('Contents to be supported'),
        description=_('Contents can be supported by users.'),
        missing=[]
    )

    content_to_examine = colander.SchemaNode(
        colander.Set(),
        widget=content_types_choices,
        title=_('Contents to be examined'),
        description=_('Contents must be examined by a review committee.'),
        missing=[]
    )

    proposal_template = colander.SchemaNode(
        ObjectData(File),
        widget=get_file_widget(file_extensions=['html']),
        title=_('Proposal template'),
        missing=None,
        description=_("Only HTML files are supported."),
        )

    work_modes = colander.SchemaNode(
        colander.Set(),
        title=_('Work modes'),
        description=_('Work modes of the working group (for proposals).'),
        widget=modes_choice,
        default=[],
    )

    nonproductive_cycle_nb = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(1, 10),
        title=_('Number of non-productive cycles'),
        description=_('The number of non-productive improvement cycles before the closure of the working group.'),
        default=3,
        )

    can_submit_directly = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(),
        label=_('Allow direct submission of proposal'),
        description=_('Members can submit directly the proposal.'),
        title='',
        missing=False
    )

    period_validity_decision = colander.SchemaNode(
        colander.Int(),
        title=_('Period of validity of the decision'),
        default=3,
        missing=3
    )


@colander.deferred
def anonymisation_kind_widget(node, kw):
    request = node.bindings['request']
    root = node.bindings['context']
    values = core.AnonymisationKinds.get_items().items()
    return deform.widget.RadioChoiceWidget(
            values=values,
            item_css_class='conf-form-anonymisation-kind')


class UserParamsConfigurationSchema(Schema):

    only_invitation = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(),
        label=_('By invitation only'),
        description=_('Users can register by invitation only.'),
        title='',
        missing=False
    )

    moderate_registration = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(),
        label=_('Moderate user registration'),
        description=_('Moderate user registration.'),
        title='',
        missing=False
    )

    duration_moderation_vote = colander.SchemaNode(
        colander.Int(),
        title=_('Vote duration'),
        description=_('The voting duration is defined by a number of days.'),
        default=7,
        missing=7
    )

    trusted_emails = colander.SchemaNode(
        colander.Set(),
        widget=Select2Widget(
            values=[],
            create=True,
            multiple=True),
        title=_('Trusted email addresses'),
        description=_("To add trusted email addresses, you need to tap the « Enter »"
                      " key after each email address or to separate them with commas."),
        missing=[]
        )

    only_for_members = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(),
        label=_('Accessible by Members only'),
        description=_('Contents can be displayed by Member sonly.'),
        title='',
        missing=False
    )

    working_group_composition_control = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(),
        label=_('Control the composition of the working group'),
        description=_('The composition of the Working Group can be controlled by its members.'),
        title='',
        missing=False
    )

    time_constant = colander.SchemaNode(
        colander.Int(),
        title=_('Time constant'),
        description=_('The time constant is defined by a number of days.'),
        default=90,
        missing=90
    )

    participants_mini = colander.SchemaNode(
        colander.Integer(),
        title=_('Minimum number of participants for a working group'),
        default=3,
        )

    anonymisation = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(
            item_css_class='conf-form-anonymisation'),
        label=_('Users can be anonymous'),
        description=_('Users can submit content anonymously.'),
        title='',
        missing=False
    )

    anonymisation_kind = colander.SchemaNode(
        colander.String(),
        widget=anonymisation_kind_widget,
        description=_('Choose the anonymization kind.'),
        title=_('Anonymization kind'),
        default='anonymity'
    )

    participants_maxi = colander.SchemaNode(
        colander.Integer(),
        title=_('Maximum number of Participants per Working Group'),
        default=12,
        )

    participations_maxi = colander.SchemaNode(
        colander.Integer(),
        title=_('Maximum number of Working Groups per Member'),
        default=5,
        )

    tokens_mini = colander.SchemaNode(
        colander.Integer(),
        title=_('Minimum number of evaluation Tokens allocated to a Member'),
        default=7,
        )

    nb_reports_maxi = colander.SchemaNode(
        colander.Integer(),
        title=_('Maximum number of reports per week'),
        default=3,
        )

    nb_submission_maxi = colander.SchemaNode(
        colander.Integer(),
        title=_('Maximum number of idea submission per week'),
        default=3,
        )

    tquarantaine = colander.SchemaNode(
        colander.Integer(),
        title=_('Delays before deleting deactivated user data'),
        default=180,
        )


@colander.deferred
def descriptions_default(node, kw):
    values = DEFAULT_EVENTS_DESCRIPTIONS.copy()
    values = sorted(values, key=lambda e: e['locale'])
    return values


class EventDescriptionTemplate(Schema):

    locale = colander.SchemaNode(
        colander.String(),
        title=_('Language'),
        widget=locale_widget,
        validator=colander.OneOf(AVAILABLE_LANGUAGES),
    )

    template = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.TextAreaWidget(rows=4, cols=60),
        title=_("Template")
        )


class EventsInterfaceConfigurationSchema(Schema):

    nb_event_maxi = colander.SchemaNode(
        colander.Integer(),
        title=_('Maximum number of events per Member'),
        default=7,
        )

    event_descriptions = colander.SchemaNode(
        colander.Sequence(),
        omit(select(EventDescriptionTemplate(
            name='description',
            title=_('Description'),
            widget=SimpleMappingWidget(
                     css_class="object-well default-well mail-template-well mail-template-block")),
            ['locale', 'template']),
                    ['_csrf_token_']),
        widget=SequenceWidget(
            min_len=1,
            max_len=len(AVAILABLE_LANGUAGES),
            add_subitem_text_template=_('Add a new description')),
        title=_('Descriptions'),
        default=descriptions_default
        )


class UserInterfaceConfigurationSchema(Schema):

    picture = colander.SchemaNode(
        ObjectData(File),
        widget=get_file_widget(file_extensions=['png', 'jpg', 'svg']),
        title=_('Logo'),
        missing=None,
        description=_("Only PNG and SVG files are supported."),
        )

    favicon = colander.SchemaNode(
        ObjectData(File),
        widget=get_file_widget(file_extensions=['ico']),
        title=_('Favicon'),
        missing=None,
        description=_("Only ICO files are supported."),
        )

    theme = colander.SchemaNode(
        ObjectData(File),
        widget=get_file_widget(file_extensions=['css']),
        title=_('Theme'),
        missing=None,
        description=_("Only CSS files are supported."),
        )

    social_share = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(),
        label=_('Activate the sharing on social networks'),
        title='',
        missing=False
        )


class HomepageConfigurationSchema(Schema):

    homepage_picture = colander.SchemaNode(
        ObjectData(File),
        widget=get_file_widget(file_extensions=['png', 'jpg', 'svg']),
        title=_('Picture of the homepage'),
        missing=None,
        description=_("Only PNG and SVG files are supported."),
        )

    homepage_text = colander.SchemaNode(
        colander.String(),
        widget=RichTextWidget(),
        title=_("Text"),
        missing=''
        )


@colander.deferred
def templates_widget(node, kw):
    len_templates = len(DEFAULT_SITE_MAILS)
    return SequenceWidget(min_len=len_templates, max_len=len_templates)


@colander.deferred
def templates_default(node, kw):
    request = node.bindings['request']
    localizer = request.localizer
    values = []
    for temp_id in DEFAULT_SITE_MAILS:
        template = DEFAULT_SITE_MAILS[temp_id].copy()
        template['mail_id'] = temp_id
        template['title'] = localizer.translate(template['title'])
        template['languages'] = list(template['languages'].values())
        values.append(template)

    values = sorted(values, key=lambda e: e['mail_id'])
    return values


class MailTemplate(Schema):

    locale = colander.SchemaNode(
        colander.String(),
        title=_('Language'),
        widget=locale_widget,
        validator=colander.OneOf(AVAILABLE_LANGUAGES),
    )

    subject = colander.SchemaNode(
        colander.String(),
        title=_('Subject'),
        )

    template = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.TextAreaWidget(rows=4, cols=60),
        title=_("Template")
        )


class MailSeqTemplate(Schema):

    mail_id = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.HiddenWidget(),
        title=_('Mail id'),
        )

    title = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.TextInputWidget(template='readonly/textinput'),
        title=_('Title'),
        missing=""
        )

    languages = colander.SchemaNode(
        colander.Sequence(),
        omit(select(MailTemplate(name='language',
                                 title=_('language'),
                                 widget=SimpleMappingWidget(
                                         css_class="object-well default-well mail-template-well mail-template-block")),
                        ['locale', 'subject', 'template']),
                    ['_csrf_token_']),
        widget=SequenceWidget(
            min_len=1,
            max_len=len(AVAILABLE_LANGUAGES),
            add_subitem_text_template=_('Add a new language')),
        title=_('Languages'),
        )


class MailTemplatesConfigurationSchema(Schema):

    mail_templates = colander.SchemaNode(
        colander.Sequence(),
        omit(select(MailSeqTemplate(name='template',
                                 title=_('E-mail template'),
                                 widget=SimpleMappingWidget(
                                         css_class="object-well default-well mail-template-well mail-template-block")),
                        ['mail_id', 'title', 'languages']),
                    ['_csrf_token_']),
        widget=templates_widget,
        default=templates_default,
        missing=templates_default,
        title=_('E-mail templates'),
        )


@colander.deferred
def keyword_widget(node, kw):
    request = node.bindings['request']
    root = request.root
    can_create = 0
    levels = root.get_tree_nodes_by_level()
    return KeywordsTreeWidget(
        min_len=1,
        max_len=DEFAULT_TREE_LEN,
        can_create=can_create,
        levels=levels)


@colander.deferred
def keywords_validator(node, kw):
    if DEFAULT_TREE == kw or tree_min_len(kw) < 2:
        raise colander.Invalid(
            node, _('Minimum one keyword required. You can specify a second keyword level for each keyword chosen.'))


class KeywordsConfSchema(Schema):

    tree = colander.SchemaNode(
        typ=DictSchemaType(),
        validator=colander.All(keywords_validator),
        widget=keyword_widget,
        default=DEFAULT_TREE,
        title=_('Keywords'),
        )

    can_add_keywords = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(),
        label=_('Authorize the addition of keywords'),
        title='',
        default=True,
        missing=True
    )

    @invariant
    def contact_invariant(self, appstruct):
        can_add_keywords = appstruct.get('can_add_keywords', 'false')
        can_add_keywords = False if can_add_keywords == 'false' else True
        keywords = appstruct.get('tree', colander.null)
        if not can_add_keywords and keywords is colander.null:
            raise colander.Invalid(
                self, _('You must enter at least one keyword.'))


class OtherSchema(Schema):

    title = colander.SchemaNode(
        colander.String(),
        title=_('Title'),
        description=_("The title of the application"),
        missing=""
        )

    locale = colander.SchemaNode(
        colander.String(),
        title=_('Locale'),
        widget=locale_widget,
        missing=locale_missing,
        validator=colander.OneOf(AVAILABLE_LANGUAGES),
    )

    contacts = colander.SchemaNode(
        colander.Sequence(),
        omit(select(ContactSchema(name='contact',
                                  widget=SimpleMappingWidget(
                                  css_class='contact-well object-well default-well')),
                    ['title', 'address', 'phone', 'surtax', 'email', 'website', 'fax']),
            ['_csrf_token_']),
        widget=SequenceWidget(
            add_subitem_text_template=_('Add a new contact')),
        title='Contacts',
        oid='contacts'
        )

    analytics = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.TextAreaWidget(rows=4, cols=60),
        title=_('Analytics'),
        missing=''
        )


class NotificationConfigurationSchema(Schema):
    """Schema for site configuration."""

    activate_push_notification = colander.SchemaNode(
        colander.Boolean(),
        widget=deform.widget.CheckboxWidget(),
        label=_('Activate the push notifications on the browser'),
        title='',
        missing=False
    )

    app_id = colander.SchemaNode(
        colander.String(),
        title=_('Application id'),
        missing=""
        )

    app_key = colander.SchemaNode(
        colander.String(),
        title=_('REST API Key'),
        missing=""
        )
