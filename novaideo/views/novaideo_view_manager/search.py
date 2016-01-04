# -*- coding: utf8 -*-
# Copyright (c) 2014 by Ecreall under licence AGPL terms
# avalaible on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import colander
from pyramid.view import view_config
from pyramid.threadlocal import get_current_request

from substanced.util import Batch

from dace.objectofcollaboration.principal.util import has_role
from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from dace.util import getSite
from dace.objectofcollaboration.principal.util import get_current
from pontus.view import BasicView
from pontus.widget import CheckboxChoiceWidget
from pontus.schema import Schema
from pontus.form import FormView

from novaideo.content.processes.novaideo_view_manager.behaviors import Search
from novaideo.content.novaideo_application import NovaIdeoApplication
from novaideo import _
from .widget import SearchTextInputWidget, SearchFormWidget
from novaideo.core import BATCH_DEFAULT_SIZE
from novaideo.content.processes import get_states_mapping
from novaideo.views.filter import (
    get_filter, FilterView, FILTER_SOURCES,
    merge_with_filter_view, find_entities)
from novaideo.content.idea import Idea
from novaideo.content.proposal import Proposal
from novaideo.content.person import Person



CONTENTS_MESSAGES = {
    '0': _(u"""No element found"""),
    '1': _(u"""One element found"""),
    '*': _(u"""${nember} elements found""")
}

DEFAULT_SEARCHABLE_CONTENT = [('idea', Idea),
                              ('proposal', Proposal),
                              ('person', Person)
                            ]


def get_default_searchable_content(request=None):
    if request is None:
        request = get_current_request()

    if getattr(request, 'is_idea_box', False):
        return [c for c in DEFAULT_SEARCHABLE_CONTENT
                if c[0] != 'proposal']

    return DEFAULT_SEARCHABLE_CONTENT


@view_config(
    name='advanced_search',
    renderer='pontus:templates/views_templates/grid.pt',
    )
class AdvancedSearchView(FilterView):
    title = _('Advanced search')
    name = 'advanced_search'
    behaviors = [Search]
    formid = 'formadvanced_search'
    wrapper_template = 'pontus:templates/views_templates/view_wrapper.pt'

    def update(self):
        self.calculate_posted_filter()
        if self.validated:
            result_view = SearchResultView(self.context, self.request)
            result_view.validated = self.validated
            result = result_view.update()
            return result
        else:
            return super(AdvancedSearchView, self).update()

    def before_update(self):
        if has_role(role=('PortalManager', )):
            self.select_filters(
                ['metadata_filter', 'geographic_filter',
                 'contribution_filter', 'temporal_filter',
                 'text_filter', 'other_filter'])

        super(AdvancedSearchView, self).before_update()


@colander.deferred
def content_types_choices(node, kw):
    request = node.bindings['request']
    return CheckboxChoiceWidget(values=get_default_searchable_content(request),
                                inline=True,
                                css_class='search-choice',
                                item_css_class="search-choices")


@colander.deferred
def default_content_types_choices(node, kw):
    request = node.bindings['request']
    return [k[0] for k in get_default_searchable_content(request)]


@colander.deferred
def text_to_search_widget(node, kw):
    request = node.bindings['request']
    choices = [{'id': 'search-choice-'+k[0],
               'title': k[1].type_title,
               'icon': k[1].icon,
               'order': index} for index, k
               in enumerate(get_default_searchable_content(request))]
    choices = sorted(
        choices, key=lambda v: v['order'])
    advanced_search_url = request.resource_url(
        request.root, '@@advanced_search')
    return SearchTextInputWidget(
        button_type='submit',
        description=_("The keyword search is done using"
                      " commas between keywords."),
        advanced_search_url=advanced_search_url,
        placeholder=_("Search"),
        choices=choices)


class SearchSchema(Schema):
    widget = SearchFormWidget()

    content_types = colander.SchemaNode(
        colander.Set(),
        widget=content_types_choices,
        title='',
        default=default_content_types_choices,
        missing=default_content_types_choices,
        )

    text_to_search = colander.SchemaNode(
        colander.String(),
        widget=text_to_search_widget,
        title='',
        missing='',
        )


@view_config(
    name='search',
    renderer='pontus:templates/views_templates/grid.pt',
    )
class SearchView(FormView):
    title = _('Search')
    name = 'search'
    coordinates = 'header'
    schema = SearchSchema()
    behaviors = [Search]
    formid = 'formsearch'
    wrapper_template = 'daceui:templates/simple_view_wrapper.pt'

    def calculate_posted_filter(self):
        post = getattr(self, 'postedform', self.request.POST or self.request.GET or {})
        form, reqts = self._build_form()
        form.formid = self.viewid + '_' + form.formid
        posted_formid = None
        default_content = [key[0] for key in get_default_searchable_content(self.request)]
        default_content.remove("person")
        if '__formid__' in post:
            posted_formid = post['__formid__']

        if posted_formid is not None and posted_formid == form.formid:
            try:
                post = post.copy()
                controls = post.items()
                validated = form.validate(controls)
                self.executed = True
                if 'content_types' in validated:
                    return {'metadata_filter':
                                {'content_types': validated['content_types']},
                            'text_filter':
                                {'text_to_search': validated['text_to_search']}}
                else:
                    return {'metadata_filter':
                                {'content_types': default_content},
                            'text_filter':
                                {'text_to_search': validated['text_to_search']}}
            except Exception:
                pass

        content_types = self.params('content_types')
        text = self.params('text_to_search')
        if content_types is not None or text is not None:
            self.executed = True

        if text is None:
            text = ''

        if content_types is None:
            content_types = default_content
        elif not isinstance(content_types, (list, tuple)):
            content_types = [content_types]

        return {'metadata_filter': {'content_types': content_types},
                'text_filter': {'text_to_search': text}}

    def before_update(self):
        root = getSite()
        self.action = self.request.resource_url(root, '')

    def default_data(self):
        appstruct = self.calculate_posted_filter()
        return {'content_types': appstruct.get(
                    'metadata_filter', {}).get('content_types', []),
                'text_to_search': appstruct.get(
                    'text_filter', {}).get('text_to_search', '')}


@view_config(
    name='',
    context=NovaIdeoApplication,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class SearchResultView(BasicView):
    title = _('Nova-Ideo contents')
    name = ''
    validators = [Search.get_validator()]
    template = 'novaideo:views/novaideo_view_manager/templates/search_result.pt'
    viewid = 'search_result'

    def _add_filter(self, user):
        def source(**args):
            default_content = [key[0] for key in
                               get_default_searchable_content(self.request)]
            default_content.remove("person")
            filter_ = {
                'metadata_filter': {'content_types': default_content}
            }
            objects = find_entities(user=user, filters=[filter_], **args)
            return objects

        url = self.request.resource_url(self.context, '@@novaideoapi')
        select = ['metadata_filter', 'geographic_filter',
                  'contribution_filter',
                  ('temporal_filter', ['negation', 'created_date']),
                  'text_filter', 'other_filter']
        return get_filter(
            self,
            url=url,
            source=source,
            select=select,
            filter_source="search_source")

    def update(self):
        user = get_current()
        validated = getattr(self, 'validated', {})
        not_validated = True if not validated else False
        posted = self.request.POST or self.request.GET or {}
        posted = posted.copy()
        executed = not not_validated
        if not_validated:
            formviewinstance = SearchView(self.context, self.request)
            formviewinstance.postedform = posted
            validated = formviewinstance.calculate_posted_filter()
            executed = getattr(formviewinstance, 'executed', False)

        filter_form = None
        if not executed or self.params('filter_result'):
            filter_form, filter_data = self._add_filter(user)
            default_content = [key[0] for key in
                               get_default_searchable_content(self.request)]
            default_content.remove("person")
            filter_ = {
                'metadata_filter': {'content_types': default_content}
            }
            validated = merge_with_filter_view(self, {})
            validated['request'] = self.request
            validated['filters'] = [filter_]

        objects = find_entities(
            user=user,
            sort_on='release_date', reverse=True,
            **validated)
        url = self.request.resource_url(self.context, self.request.view_name,
                                        query=posted)
        batch = Batch(objects,
                      self.request,
                      url=url,
                      default_size=BATCH_DEFAULT_SIZE)
        batch.target = "#results"
        len_result = batch.seqlen
        index = str(len_result)
        if len_result > 1:
            index = '*'

        self.title = _(CONTENTS_MESSAGES[index],
                       mapping={'nember': len_result})

        filter_instance = getattr(self, 'filter_instance', None)
        filter_body = None
        if filter_instance:
            filter_data['filter_message'] = self.title
            filter_body = filter_instance.get_body(filter_data)

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
        if filter_form:
            result['css_links'] = filter_form['css_links']
            result['js_links'] = filter_form['js_links']

        return result


DEFAULTMAPPING_ACTIONS_VIEWS.update({Search: SearchView})


FILTER_SOURCES.update(
    {"search_source": SearchResultView})
