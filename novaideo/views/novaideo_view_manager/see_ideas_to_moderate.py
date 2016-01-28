# Copyright (c) 2014 by Ecreall under licence AGPL terms 
# avalaible on http://www.gnu.org/licenses/agpl.html 

# licence: AGPL
# author: Amen Souissi

from pyramid.view import view_config

from substanced.util import Batch

from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from dace.objectofcollaboration.principal.util import get_current
from pontus.view import BasicView

from novaideo.content.processes.novaideo_view_manager.behaviors import (
    SeeIdeasToModerate)
from novaideo.core import BATCH_DEFAULT_SIZE
from novaideo.content.novaideo_application import NovaIdeoApplication
from novaideo.content.processes import get_states_mapping
from novaideo import _
from novaideo.views.filter import (
    get_filter, FILTER_SOURCES, merge_with_filter_view, find_entities)


CONTENTS_MESSAGES = {
    '0': _(u"""No idea found"""),
    '1': _(u"""One idea found"""),
    '*': _(u"""${nember} ideas found""")
    }


@view_config(
    name='seeideastomoderate',
    context=NovaIdeoApplication,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class SeeIdeasToModerateView(BasicView):
    title = _('Ideas to moderate')
    name = 'seeideastomoderate'
    behaviors = [SeeIdeasToModerate]
    template = 'novaideo:views/novaideo_view_manager/templates/search_result.pt'
    viewid = 'seeideastomoderate'

    def _add_filter(self, user):
        def source(**args):
            filters = [
                {'metadata_filter': {
                    'content_types': ['idea'],
                    'states': ['submitted']
                }}
            ]
            objects = find_entities(
                user=user, include_site=True, filters=filters, **args)
            return objects

        url = self.request.resource_url(self.context, '@@novaideoapi')
        return get_filter(
            self,
            url=url,
            source=source,
            select=[('metadata_filter', ['keywords']),
                    'contribution_filter', ('temporal_filter', ['negation', 'created_date']),
                    'text_filter', 'other_filter'])

    def update(self):
        self.execute(None)
        user = get_current()
        filter_form, filter_data = self._add_filter(user)
        filters = [
            {'metadata_filter': {
                'content_types': ['idea'],
                'states': ['submitted']
            }}
        ]
        args = {}
        args = merge_with_filter_view(self, args)
        args['request'] = self.request
        objects = find_entities(
            user=user,
            filters=filters,
            **args)
        url = self.request.resource_url(self.context, 'seeideastomoderate')
        batch = Batch(objects, self.request,
                      url=url,
                      default_size=BATCH_DEFAULT_SIZE)
        batch.target = "#results_contents"
        len_result = batch.seqlen
        index = str(len_result)
        if len_result > 1:
            index = '*'

        self.title = _(CONTENTS_MESSAGES[index],
                       mapping={'nember': len_result})
        filter_data['filter_message'] = self.title
        filter_body = self.filter_instance.get_body(filter_data)
        result_body = []
        for obj in batch:
            render_dict = {'object': obj,
                           'current_user': user,
                           'state': get_states_mapping(user, obj,
                                   getattr(obj, 'state_or_none', [None])[0])}
            body = self.content(args=render_dict,
                                template=obj.templates['default'])['body']
            result_body.append(body)

        result = {}
        values = {'bodies': result_body,
                  'batch': batch,
                  'filter_body': filter_body}
        body = self.content(args=values, template=self.template)['body']
        item = self.adapt_item(body, self.viewid)
        result['coordinates'] = {self.coordinates: [item]}
        result['css_links'] = filter_form['css_links']
        result['js_links'] = filter_form['js_links']
        return result


DEFAULTMAPPING_ACTIONS_VIEWS.update(
    {SeeIdeasToModerate: SeeIdeasToModerateView})


FILTER_SOURCES.update(
    {SeeIdeasToModerateView.name: SeeIdeasToModerateView})