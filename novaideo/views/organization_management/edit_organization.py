# Copyright (c) 2014 by Ecreall under licence AGPL terms 
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import deform
from pyramid.view import view_config

from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from pontus.form import FormView
from pontus.schema import select
from pontus.default_behavior import Cancel

from novaideo.content.processes.organization_management.behaviors import (
    EditOrganization)
from novaideo.content.organization import OrganizationSchema, Organization
from novaideo import _


@view_config(
    name='editorganization',
    context=Organization,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class EditOrganizationView(FormView):

    title = _('Edit the organization')
    schema = select(OrganizationSchema(editable=True),
                    ['title',
                     'description',
                     'logo',
                     'cover_picture',
                     'managers',
                     'contacts'])
    behaviors = [EditOrganization, Cancel]
    formid = 'formeditorganization'
    name = 'editorganization'
    css_class = 'panel-transparent'

    def default_data(self):
        return self.context

    def before_update(self):
        self.action = self.request.resource_url(
            self.context, 'novaideoapi',
            query={'op': 'update_action_view',
                   'node_id': EditOrganization.node_definition.id})
        self.schema.widget = deform.widget.FormWidget(
            css_class='deform novaideo-ajax-form')


DEFAULTMAPPING_ACTIONS_VIEWS.update({EditOrganization: EditOrganizationView})
