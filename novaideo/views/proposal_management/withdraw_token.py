from pyramid.view import view_config

from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from pontus.view import BasicView

from novaideo.content.processes.proposal_management.behaviors import  WithdrawToken
from novaideo.content.proposal import Proposal
from novaideo import _


@view_config(
    name='withdrawtoken',
    context=Proposal,
    renderer='pontus:templates/view.pt',
    )
class WithdrawTokenView(BasicView):
    title = _('Withdraw my token')
    name = 'withdrawtoken'
    behaviors = [WithdrawToken]
    viewid = 'withdrawtoken'


    def update(self):
        self.execute(None)        
        return list(self.behaviorinstances.values())[0].redirect(self.context, self.request)

DEFAULTMAPPING_ACTIONS_VIEWS.update({WithdrawToken:WithdrawTokenView})
