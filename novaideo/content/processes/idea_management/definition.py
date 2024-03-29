# Copyright (c) 2014 by Ecreall under licence AGPL terms
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi
"""
This module represent the Idea management process definition
powered by the dace engine. This process is unique, which means that
this process is instantiated only once.
"""
from dace.processdefinition.processdef import ProcessDefinition
from dace.processdefinition.activitydef import ActivityDefinition
from dace.processdefinition.gatewaydef import (
    ExclusiveGatewayDefinition,
    ParallelGatewayDefinition)
from dace.processdefinition.transitiondef import TransitionDefinition
from dace.processdefinition.eventdef import (
    StartEventDefinition,
    EndEventDefinition)
from dace.objectofcollaboration.services.processdef_container import (
    process_definition)
from pontus.core import VisualisableElement

from .behaviors import (
    CreateIdea,
    CrateAndPublish,
    CrateAndPublishAsProposal,
    SeeRelatedWorkingGroups,
    DuplicateIdea,
    DelIdea,
    EditIdea,
    PublishIdea,
    RecuperateIdea,
    AbandonIdea,
    CommentIdea,
    CommentIdeaAnonymous,
    PresentIdea,
    PresentIdeaAnonymous,
    Associate,
    SeeIdea,
    CompareIdea,
    SubmitIdea,
    SubmitIdeaMax,
    ArchiveIdea,
    OpposeIdea,
    SupportIdea,
    WithdrawToken,
    MakeOpinion,
    ModerationVote)
from novaideo import _
from novaideo.content.idea import Idea
from novaideo.content.processes.content_ballot_management import (
    BALLOT_DATA)
from novaideo.content.processes.content_ballot_management.definition import (
    ContentBallot)
from novaideo.content.processes.reports_management.definition import (
    IDEA_MODERATION_GROUP)


@process_definition(name='ideamanagement', id='ideamanagement')
class IdeaManagement(ProcessDefinition, VisualisableElement):
    isUnique = True

    def __init__(self, **kwargs):
        super(IdeaManagement, self).__init__(**kwargs)
        self.title = _('Ideas management')
        self.description = _('Ideas management')

    def _init_definition(self):
        self.defineNodes(
                start = StartEventDefinition(),
                #egs = ExclusiveGatewayDefinition(),
                creat = ActivityDefinition(contexts=[CreateIdea],
                                       description=_("Create an idea"),
                                       title=_("Create an idea"),
                                       groups=[_('Add')]),
                creatandpublish = ActivityDefinition(contexts=[CrateAndPublish],
                                       description=_("Create an idea"),
                                       title=_("Create an idea"),
                                       groups=[]),
                creatandpublishasproposal = ActivityDefinition(contexts=[CrateAndPublishAsProposal],
                                       description=_("Create a Working Group"),
                                       title=_("Create a Working Group"),
                                       groups=[]),
                duplicate = ActivityDefinition(contexts=[DuplicateIdea],
                                       description=_("Duplicate this idea"),
                                       title=_("Duplicate"),
                                       groups=[]),
                delidea = ActivityDefinition(contexts=[DelIdea],
                                       description=_("Delete the idea"),
                                       title=_("Delete"),
                                       groups=[]),
                edit = ActivityDefinition(contexts=[EditIdea],
                                       description=_("Edit the idea"),
                                       title=_("Edit"),
                                       groups=[]),
                submit = ActivityDefinition(contexts=[SubmitIdea],
                                       description=_("Submit the idea"),
                                       title=_("Submit for publication"),
                                       groups=[]),
                submit_max = ActivityDefinition(contexts=[SubmitIdeaMax],
                                       description=_("Submit the idea"),
                                       title=_("Submit for publication"),
                                       groups=[]),
                archive = ActivityDefinition(contexts=[ArchiveIdea],
                                       description=_("Archive the idea"),
                                       title=_("Archive"),
                                       groups=[]),
                publish = ActivityDefinition(contexts=[PublishIdea],
                                       description=_("Publish the idea"),
                                       title=_("Publish"),
                                       groups=[]),
                recuperate = ActivityDefinition(contexts=[RecuperateIdea],
                                       description=_("Restore the idea"),
                                       title=_("Restore"),
                                       groups=[]),
                abandon = ActivityDefinition(contexts=[AbandonIdea],
                                       description=_("Archive the idea"),
                                       title=_("Archive"),
                                       groups=[]),
                present = ActivityDefinition(contexts=[PresentIdea, PresentIdeaAnonymous],
                                       description=_("Share the idea with others"),
                                       title=_("Share"),
                                       groups=[]),
                comment = ActivityDefinition(contexts=[CommentIdea, CommentIdeaAnonymous],
                                       description=_("Comment the idea"),
                                       title=_("Comment"),
                                       groups=[]),
                associate = ActivityDefinition(contexts=[Associate],
                                       description=_("Associate the idea"),
                                       title=_("Associate"),
                                       groups=[]),
                see = ActivityDefinition(contexts=[SeeIdea],
                                       description=_("Details"),
                                       title=_("Details"),
                                       groups=[]),
                compare = ActivityDefinition(contexts=[CompareIdea],
                                       description=_("Compare versions"),
                                       title=_("Compare"),
                                       groups=[]),
                support = ActivityDefinition(contexts=[SupportIdea],
                                       description=_("Support the idea"),
                                       title=_("Support"),
                                       groups=[]),
                oppose = ActivityDefinition(contexts=[OpposeIdea],
                                       description=_("Oppose the idea"),
                                       title=_("Oppose"),
                                       groups=[]),
                withdraw_token = ActivityDefinition(contexts=[WithdrawToken],
                                       description=_("Withdraw the support token from the idea"),
                                       title=_("Withdraw my token"),
                                       groups=[]),
                makeitsopinion = ActivityDefinition(contexts=[MakeOpinion],
                                       description=_("Give one's opinion"),
                                       title=_("Give one's opinion"),
                                       groups=[]),
                seeworkinggroups = ActivityDefinition(contexts=[SeeRelatedWorkingGroups],
                                       description=_("See the related working groups"),
                                       title=_("The working groups"),
                                       groups=[]),
                pg = ParallelGatewayDefinition(),
                eg = ExclusiveGatewayDefinition(),
                end = EndEventDefinition(),
        )
        self.defineTransitions(
                TransitionDefinition('start', 'pg'),
                TransitionDefinition('pg', 'creat'),
                TransitionDefinition('pg', 'creatandpublish'),
                TransitionDefinition('pg', 'seeworkinggroups'),
                TransitionDefinition('pg', 'creatandpublishasproposal'),
                TransitionDefinition('pg', 'duplicate'),
                TransitionDefinition('pg', 'edit'),
                TransitionDefinition('pg', 'publish'),
                TransitionDefinition('pg', 'delidea'),
                TransitionDefinition('pg', 'abandon'),
                TransitionDefinition('pg', 'recuperate'),
                TransitionDefinition('pg', 'comment'),
                TransitionDefinition('pg', 'present'),
                TransitionDefinition('pg', 'associate'),
                TransitionDefinition('pg', 'see'),
                TransitionDefinition('pg', 'compare'),
                TransitionDefinition('pg', 'submit'),
                TransitionDefinition('pg', 'submit_max'),
                TransitionDefinition('pg', 'archive'),
                TransitionDefinition('pg', 'makeitsopinion'),
                TransitionDefinition('makeitsopinion', 'eg'),
                TransitionDefinition('pg', 'support'),
                TransitionDefinition('support', 'eg'),
                TransitionDefinition('pg', 'oppose'),
                TransitionDefinition('oppose', 'eg'),
                TransitionDefinition('pg', 'withdraw_token'),
                TransitionDefinition('withdraw_token', 'eg'),
                TransitionDefinition('creat', 'eg'),
                TransitionDefinition('creatandpublish', 'eg'),
                TransitionDefinition('creatandpublishasproposal', 'eg'),
                TransitionDefinition('duplicate', 'eg'),
                TransitionDefinition('recuperate', 'eg'),
                TransitionDefinition('abandon', 'eg'),
                TransitionDefinition('publish', 'eg'),
                TransitionDefinition('delidea', 'eg'),
                TransitionDefinition('edit', 'eg'),
                TransitionDefinition('comment', 'eg'),
                TransitionDefinition('present', 'eg'),
                TransitionDefinition('associate', 'eg'),
                TransitionDefinition('see', 'eg'),
                TransitionDefinition('compare', 'eg'),
                TransitionDefinition('submit', 'eg'),
                TransitionDefinition('submit_max', 'eg'),
                TransitionDefinition('archive', 'eg'),
                TransitionDefinition('seeworkinggroups', 'eg'),
                TransitionDefinition('eg', 'end'),
        )


def idea_title(process, context):
    return _("Vote to Moderate a new Idea « ${idea} »",
             mapping={'idea': context.title})


BALLOT_DATA[Idea.__name__+'-ideamoderation'] = {
    'ballot_description_template': 'novaideo:views/templates/ballots/moderate_idea.pt',
    'ballot_title': idea_title,
    'true_value': _("This new Idea complies with the Moderation Charter"),
    'false_value': _("This new Idea DOES NOT comply with the Moderation Charter"),
    'process_id': 'ideamoderation',
    'group': IDEA_MODERATION_GROUP
}


@process_definition(
    name='ideamoderation',
    id='ideamoderation')
class IdeaModeration(ContentBallot):
    ballot_action = ModerationVote

    def __init__(self, **kwargs):
        super(IdeaModeration, self).__init__(**kwargs)
