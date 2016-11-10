# Copyright (c) 2014 by Ecreall under licence AGPL terms
# avalaible on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

from pyramid.view import view_config

from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from pontus.default_behavior import Cancel
from pontus.form import FormView
from pontus.view import BasicView
from pontus.schema import select

from novaideo.content.processes.user_management.behaviors import (
    Registration)
from novaideo.content.person import PersonSchema, Preregistration
from novaideo.content.novaideo_application import (
    NovaIdeoApplication)
from novaideo import _


@view_config(
    name='registration',
    context=NovaIdeoApplication,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class RegistrationView(FormView):

    title = _('Your registration')
    schema = select(PersonSchema(factory=Preregistration,
                                 editable=True),
                    ['user_title',
                     'first_name',
                     'last_name',
                     'birth_date',
                     'email',
                     'Keep_me_anonymous',
                     'pseudonym',
                     'accept_conditions'])
    behaviors = [Registration, Cancel]
    formid = 'formregistration'
    name = 'registration'
    requirements = {'css_links': [],
                    'js_links': ['novaideo:static/js/user_management.js']}


@view_config(
    name='registrationsubmitted',
    context=NovaIdeoApplication,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class RegistrationSubmittedView(BasicView):
    template = 'novaideo:views/user_management/templates/registrationsubmitted.pt'
    title = _('Please confirm your registration')
    name = 'registrationsubmitted'
    viewid = 'deactivateview'

    def before_update(self):
        moderate_registration = getattr(
            self.context, 'moderate_registration', False)
        if moderate_registration:
            self.title = _('Your registration is submitted to moderation')

    def update(self):
        result = {}
        body = self.content(args={}, template=self.template)['body']
        item = self.adapt_item(body, self.viewid)
        result['coordinates'] = {self.coordinates: [item]}
        return result


DEFAULTMAPPING_ACTIONS_VIEWS.update({Registration: RegistrationView})
