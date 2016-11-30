# Copyright (c) 2014 by Ecreall under licence AGPL terms 
# avalaible on http://www.gnu.org/licenses/agpl.html 

# licence: AGPL
# author: Amen Souissi

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound

from dace.util import getSite
from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from dace.objectofcollaboration.principal.util import (
    get_current, has_any_roles)
from pontus.view import BasicView
from pontus.view_operation import MultipleView
from pontus.util import merge_dicts

from novaideo.content.processes.idea_management.behaviors import SeeIdea
from novaideo.content.idea import Idea
from novaideo.content.processes import get_states_mapping
from novaideo.utilities.util import (
    generate_navbars, ObjectRemovedException,
    get_vote_actions_body)
from novaideo import _
from .compare_idea import CompareIdeaView


_marker = object()


class DetailIdeaView(BasicView):
    title = _('Details')
    name = 'seeIdea'
    behaviors = [SeeIdea]
    template = 'novaideo:views/idea_management/templates/see_idea.pt'
    wrapper_template = 'daceui:templates/simple_view_wrapper.pt'
    viewid = 'seeidea'
    validate_behaviors = False
    requirements = {'css_links': [],
                    'js_links': ['novaideo:static/js/ballot_management.js']}

    def _cant_publish_alert(self, actions, user):
        if not self.request.moderate_ideas and \
           'to work' in self.context.state and self.context.author is user:
            return not any(a.behavior_id == 'publish'
                           for a in actions.get('global-action', []))

        return False

    def _cant_submit_alert(self, actions, user):
        if self.request.moderate_ideas and \
           'to work' in self.context.state and self.context.author is user:
            return not any(a.behavior_id == 'submit'
                           for a in actions.get('global-action', []))

        return False

    def update(self):
        self.execute(None)
        vote_actions = get_vote_actions_body(
            self.context, self.request)
        try:
            text_action = [{'title': _('Moderate'),
                            'class_css': 'vote-action',
                            'style_picto': 'glyphicon glyphicon-stats'}] \
                if vote_actions['actions'] else []
            navbars = generate_navbars(
                self.request, self.context,
                text_action=text_action)
        except ObjectRemovedException:
            return HTTPFound(self.request.resource_url(getSite(), ''))

        resources = merge_dicts(navbars['resources'], vote_actions['resources'],
                                ('js_links', 'css_links'))
        resources['js_links'] = list(set(resources['js_links']))
        resources['css_links'] = list(set(resources['css_links']))
        messages = vote_actions['messages']
        if not messages:
            messages = navbars['messages']

        user = get_current()
        files = getattr(self.context, 'attached_files', [])
        files_urls = []
        for file_ in files:
            files_urls.append({'title': file_.title,
                               'url': file_.url})

        is_censored = 'censored' in self.context.state
        to_hide = is_censored and not has_any_roles(
            user=user, roles=(('Owner', self.context), 'Moderator'))
        result = {}
        values = {
            'idea': self.context,
            'is_censored': is_censored,
            'to_hide': to_hide,
            'text': self.context.text.replace('\n', '<br/>'),
            'state': get_states_mapping(
                user, self.context, self.context.state[0]),
            'current_user': user,
            'files': files_urls,
            'cant_publish': self._cant_publish_alert(
                navbars['all_actions'], user),
            'cant_submit': self._cant_submit_alert(
                navbars['all_actions'], user),
            'navbar_body': navbars['navbar_body'],
            'footer_actions_body': navbars['footer_actions_body'],
            'actions_bodies': navbars['body_actions'],
            'footer_body': navbars['footer_body'],
            'vote_actions_body': vote_actions['body']
        }
        body = self.content(args=values, template=self.template)['body']
        item = self.adapt_item(body, self.viewid)
        item['messages'] = messages
        item['isactive'] = vote_actions['isactive'] or navbars['isactive']
        result.update(resources)
        result['coordinates'] = {self.coordinates: [item]}
        result = merge_dicts(self.requirements_copy, result)
        return result


class SeeIdeaActionsView(MultipleView):
    title = _('actions')
    name = 'seeiactionsdea'
    template = 'novaideo:views/idea_management/templates/panel_group.pt'
    views = (CompareIdeaView,)

    def _activate(self, items):
        pass


@view_config(
    name='seeidea',
    context=Idea,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class SeeIdeaView(MultipleView):
    title = ''
    name = 'seeidea'
    template = 'novaideo:views/templates/simple_mergedmultipleview.pt'
    views = (DetailIdeaView, SeeIdeaActionsView)
    requirements = {'css_links': [],
                    'js_links': ['novaideo:static/js/compare_idea.js',
                                 'novaideo:static/js/comment.js']}
    validators = [SeeIdea.get_validator()]


DEFAULTMAPPING_ACTIONS_VIEWS.update(
    {SeeIdea: SeeIdeaView})
