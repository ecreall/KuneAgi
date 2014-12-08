# Copyright (c) 2014 by Ecreall under licence AGPL terms 
# avalaible on http://www.gnu.org/licenses/agpl.html 

# licence: AGPL
# author: Amen Souissi

import deform
from deform.widget import default_resource_registry
from pyramid.threadlocal import get_current_request
from pyramid import renderers

from pontus.widget import SequenceWidget, Select2Widget



class LimitedTextAreaWidget(deform.widget.TextAreaWidget):
    template = 'novaideo:views/templates/textarea.pt'
    default_alert_template = 'novaideo:views/templates/textarea_default_alert.pt'
    requirements = ( ('jquery.maskedinput', None), 
                     ('limitedtextarea', None)) 

    @property
    def alert_message(self):
        alert_values = {'limit': self.limit}
        template = self.default_alert_template
        if hasattr(self, 'alert_template'):
            template = self.alert_template

        if hasattr(self, 'alert_values'):
            alert_values = self.alert_values

        request = get_current_request()
        body = renderers.render(
               template, alert_values, request)
        return body

class MappinColgWidget(deform.widget.MappingWidget):

    template = 'novaideo:views/templates/mapping_col.pt'


class ConfirmationWidget(deform.widget.MappingWidget):
    template = 'novaideo:views/templates/confirmation_form.pt'


class InLineWidget(SequenceWidget):

    template = 'novaideo:views/templates/inline.pt'
    item_template = 'novaideo:views/templates/inline_item.pt'


class ObjectWidget(deform.widget.MappingWidget):

    template = 'novaideo:views/templates/object_mapping.pt'
    item_template = 'novaideo:views/templates/object_mapping_item.pt'


class SimpleMappingtWidget(deform.widget.MappingWidget):
    template = 'novaideo:views/templates/mapping_simple.pt'


class Select2WidgetSearch(Select2Widget):
    template = 'novaideo:views/templates/select2.pt'
    requirements = (('deform', None), ('select2search', None))


class AddIdeaWidget(deform.widget.MappingWidget):
    template = 'novaideo:views/templates/add_idea_widget.pt'
    requirements = (('deform', None), ('addnewidea', None))


class DragDropSequenceWidget(SequenceWidget):

    template = 'novaideo:views/templates/dragdrop_sequence/sequence.pt'
    item_template = 'novaideo:views/templates/dragdrop_sequence/sequence_item.pt'


class DragDropSelect2Widget(Select2Widget):
    template = 'novaideo:views/templates/dragdrop_sequence/select2.pt'
    requirements = (('deform', None), ('select2dragdrop', None))


class DragDropMappingWidget(deform.widget.MappingWidget):

    template = 'novaideo:views/templates/dragdrop_sequence/mapping.pt'
    item_template = 'novaideo:views/templates/dragdrop_sequence/mapping_item.pt'


default_resource_registry.set_js_resources('addnewidea', None, 
                         'novaideo:static/js/add_new_idea.js'  )

default_resource_registry.set_js_resources('select2search', None, 
           'daceui:static/select2/select2.js',
           'novaideo:static/select2_search/select2_search.js'  )

default_resource_registry.set_css_resources('select2search', None, 
              'daceui:static/select2/select2.css',
              'novaideo:static/select2_search/select2_search.css'  )

default_resource_registry.set_js_resources('select2dragdrop', None, 
                'daceui:static/select2/select2.js',
                'novaideo:static/js/dragdrop_select.js'  )

default_resource_registry.set_css_resources('select2dragdrop', None, 
                'daceui:static/select2/select2.css',
                'novaideo:static/select2_search/select2_search.css'  )

default_resource_registry.set_js_resources('limitedtextarea', None, 
               'novaideo:static/limitedtextarea/limitedtextarea.js'  )

default_resource_registry.set_css_resources('limitedtextarea', None, 
              'novaideo:static/limitedtextarea/limitedtextarea.css'  )
