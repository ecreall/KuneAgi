# Copyright (c) 2014 by Ecreall under licence AGPL terms
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import colander
from pyramid.view import view_config

from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from pontus.default_behavior import Cancel
from pontus.form import FormView
from pontus.schema import Schema
from pontus.view import BasicView
from pontus.widget import Select2Widget
from pontus.view_operation import MultipleView
from deform_treepy.utilities.tree_utility import tree_to_keywords

from novaideo.content.processes.admin_process.behaviors import (
    ManageKeywords)
from novaideo.content.novaideo_application import (
    NovaIdeoApplication)
from novaideo import _
from novaideo.content.keyword import ROOT_TREE


class ManageKeywordsViewStudyReport(BasicView):
    title = 'Alert for keywords'
    name = 'alertforkeywordsmanagement'
    template = 'novaideo:views/admin_process/templates/alert_event_keywords.pt'

    def update(self):
        result = {}
        values = {}
        body = self.content(args=values, template=self.template)['body']
        item = self.adapt_item(body, self.viewid)
        result['coordinates'] = {self.coordinates: [item]}
        return result


@colander.deferred
def targets_choice(node, kw):
    request = node.bindings['request']
    root = request.root
    keywords = [kw_.split('/') for kw_ in tree_to_keywords(root.tree)]
    keywords = list(set([item for sublist in keywords for item in sublist]))
    if ROOT_TREE in keywords:
        keywords.remove(ROOT_TREE)

    values = [(v, v) for v in sorted(keywords)]
    return Select2Widget(
        values=values,
        multiple=True
        )


class ManageKeywordsSchema(Schema):

    targets = colander.SchemaNode(
        colander.Set(),
        widget=targets_choice,
        title=_("Keywords")
        )

    source = colander.SchemaNode(
        colander.String(),
        title=_("New keyword")
        )


class ManageKeywordsFormView(FormView):

    title = _('Manage keywords')
    schema = ManageKeywordsSchema()
    behaviors = [ManageKeywords, Cancel]
    formid = 'formmanagekeywords'
    name = 'formmanagekeywords'
    css_class = 'panel-transparent'


@view_config(
    name='managekeywords',
    context=NovaIdeoApplication,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class ManageKeywordsView(MultipleView):
    title = _('Manage keywords')
    name = 'managekeywords'
    viewid = 'managekeywords'
    template = 'daceui:templates/mergedmultipleview.pt'
    views = (ManageKeywordsViewStudyReport, ManageKeywordsFormView)
    validators = [ManageKeywords.get_validator()]
    css_class = 'panel-transparent'


DEFAULTMAPPING_ACTIONS_VIEWS.update({ManageKeywords: ManageKeywordsView})
