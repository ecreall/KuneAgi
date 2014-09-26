from dace.interfaces import IProcessDefinition
from dace.processdefinition.processdef import ProcessDefinition
from dace.processdefinition.activitydef import ActivityDefinition
from dace.processdefinition.gatewaydef import (
    ExclusiveGatewayDefinition, 
    ParallelGatewayDefinition)
from dace.processdefinition.transitiondef import TransitionDefinition
from dace.processdefinition.eventdef import (
    StartEventDefinition,
    EndEventDefinition,
    IntermediateCatchEventDefinition,
    ConditionalEventDefinition,
    TimerEventDefinition)
from dace.objectofcollaboration.services.processdef_container import process_definition

from pontus.core import VisualisableElement

from .behaviors import Vote
from novaideo import _



def time_duration(process):
    return getattr(process.ballot, 'duration')


@process_definition(name='fptpprocess', id='fptpprocess')
class FPTPProcess(ProcessDefinition, VisualisableElement):
    isUnique = True
    isVolatile = True
    isControlled = True
    discriminator = 'Vote process'

    def __init__(self, **kwargs):
        super(FPTPProcess, self).__init__(**kwargs)
        self.title = _('FPTP Process')
        self.description = _('FPTP Process')

    def _init_definition(self):
        self.defineNodes(
                start = StartEventDefinition(),
                eg = ExclusiveGatewayDefinition(),
                vote = ActivityDefinition(contexts=[Vote],
                                       description=_("Vote"),
                                       title=_("Vote"),
                                       groups=[]),
                timer = IntermediateCatchEventDefinition(TimerEventDefinition(time_duration=time_duration)),
                eg1 = ExclusiveGatewayDefinition(),
                end = EndEventDefinition(),
        )
        self.defineTransitions(
                TransitionDefinition('start', 'eg'),
                TransitionDefinition('eg', 'vote'),
                TransitionDefinition('eg', 'timer'),
                TransitionDefinition('vote', 'eg1'),
                TransitionDefinition('timer', 'eg1'),
                TransitionDefinition('eg1', 'end'),

        )