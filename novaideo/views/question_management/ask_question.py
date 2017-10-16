# Copyright (c) 2014 by Ecreall under licence AGPL terms 
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import deform
from pyramid.view import view_config
from pyramid.traversal import find_resource

from dace.objectofcollaboration.object import Object
from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from dace.objectofcollaboration.principal.util import get_current
from pontus.default_behavior import Cancel
from pontus.form import FormView
from pontus.schema import select, omit
from pontus.view import BasicView

from novaideo.utilities.util import render_listing_obj
from novaideo.utilities.pseudo_react import (
    get_all_updated_data, get_components_data)
from novaideo.content.processes.question_management.behaviors import (
    AskQuestion)
from novaideo.content.question import QuestionSchema, Question
from novaideo.content.challenge import Challenge
from novaideo.content.novaideo_application import NovaIdeoApplication
from novaideo import _, log
from novaideo.views.core import update_anonymous_schemanode, update_challenge_schemanode


@view_config(
    name='askquestion',
    context=NovaIdeoApplication,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class AskQuestionView(FormView):

    title = _('Ask a question')
    schema = select(QuestionSchema(factory=Question, editable=True, omit=('anonymous',)),
                    ['challenge',
                     'title',
                     'text',
                     'options',
                     'tree',
                     'attached_files',
                     'anonymous'])
    behaviors = [AskQuestion, Cancel]
    formid = 'formaskquestion'
    name = 'askquestion'
    css_class = 'panel-transparent'

    def before_update(self):
        user = get_current(self.request)
        self.schema = update_anonymous_schemanode(
            self.request.root, self.schema)
        self.schema = update_challenge_schemanode(
            self.request, user, self.schema)
        if not getattr(self, 'is_home_form', False):
            self.action = self.request.resource_url(
                self.context, 'novaideoapi',
                query={'op': 'update_action_view',
                       'node_id': AskQuestion.node_definition.id})
            self.schema.widget = deform.widget.FormWidget(
                css_class='deform novaideo-ajax-form')
        else:
            self.action = self.request.resource_url(
                self.context, 'askquestion')
            self.schema.widget = deform.widget.FormWidget(
                css_class='material-form deform')

    def bind(self):
        if getattr(self, 'is_home_form', False):
            return {'is_home_form': True}

        return {}


@view_config(name='questionsmanagement',
             context=Object,
             xhr=True,
             renderer='json')
class AskQuestionView_Json(BasicView):

    behaviors = [AskQuestion]

    def creat_home_question(self):
        try:
            view_name = self.params('source_path')
            view_name = view_name if view_name else ''
            is_mycontents_view = view_name.endswith('seemycontents')
            context = self.context
            try:
                source_path = '/'.join(view_name.split('/')[:-1])
                context = find_resource(self.context, source_path)
            except Exception as error:
                log.warning(error)

            is_challenge = isinstance(context, Challenge)
            redirect = False
            for action_id in self.behaviors_instances:
                if action_id in self.request.POST:
                    button = action_id
                    break

            add_question_action = self.behaviors_instances[button]
            add_question_view = DEFAULTMAPPING_ACTIONS_VIEWS[add_question_action.__class__]
            add_question_view_instance = add_question_view(
                self.context, self.request, behaviors=[add_question_action])
            add_question_view_instance.viewid = 'formaskquestionhome'
            add_question_view_result = add_question_view_instance()
            if add_question_view_instance.finished_successfully:
                result = get_components_data(
                    **get_all_updated_data(
                        add_question_action, self.request, self.context, self,
                        view_data=(add_question_view_instance, add_question_view_result)
                    ))
                user = get_current()
                body = ''
                if not redirect:
                    question = sorted(
                        user.get_questions(user),
                        key=lambda w: w.created_at)[-1]
                    if not is_mycontents_view and \
                       'published' not in question.state:
                        redirect = True
                    else:
                        if is_mycontents_view:
                            result['item_target'] = 'results_contents'
                        elif is_challenge:
                            result['item_target'] = 'results-challenge-questions'
                        else:
                            result['item_target'] = 'results-home-questions'

                        body += render_listing_obj(
                            self.request, question, user)

                if not redirect:
                    result['redirect_url'] = None

                result['new_obj_body'] = body
                result['status'] = True
                return result

        except Exception as error:
            log.warning(error)
            return {'status': False}

        return {'status': False}

    def __call__(self):
        operation_name = self.params('op')
        if operation_name is not None:
            operation = getattr(self, operation_name, None)
            if operation is not None:
                return operation()

        return {}


DEFAULTMAPPING_ACTIONS_VIEWS.update(
    {AskQuestion: AskQuestionView})
