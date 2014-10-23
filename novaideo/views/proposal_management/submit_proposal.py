from pyramid.view import view_config

from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from pontus.view import BasicView
from pontus.default_behavior import Cancel
from pontus.form import FormView
from pontus.view_operation import MultipleView

from novaideo.content.processes.proposal_management.behaviors import  SubmitProposal
from novaideo.content.proposal import Proposal
from novaideo import _


class SubmitProposalStudyReport(BasicView):
    title = _('Alert for explanation')
    name='alertforexplanation'
    template ='novaideo:views/proposal_management/templates/alert_submit_proposal.pt'

    def update(self):
        result = {}
        not_published_ideas = [i for i in self.context.related_ideas if not('published' in i.state)]
        values = {'ideas': not_published_ideas}
        body = self.content(result=values, template=self.template)['body']
        item = self.adapt_item(body, self.viewid)
        result['coordinates'] = {self.coordinates:[item]}
        return result

class SubmitProposalFormView(FormView):
    title = _('Submit')
    name = 'formsubmitproposal'
    behaviors = [SubmitProposal, Cancel]
    viewid = 'formsubmitproposal'
    formid = 'submitproposalform'


@view_config(
    name='submitproposal',
    context=Proposal,
    renderer='pontus:templates/view.pt',
    )
class SubmitProposalView(MultipleView):
    title = _('Submit')
    name = 'submitproposal'
    #behaviors = [SubmitProposal]
    viewid = 'submitproposal'
    template = 'pontus.dace_ui_extension:templates/mergedmultipleview.pt'
    views = (SubmitProposalStudyReport, SubmitProposalFormView)
    validators = [SubmitProposal.get_validator()]


DEFAULTMAPPING_ACTIONS_VIEWS.update({SubmitProposal:SubmitProposalView})
