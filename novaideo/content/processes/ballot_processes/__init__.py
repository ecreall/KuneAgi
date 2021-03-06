# -*- coding: utf8 -*-
# Copyright (c) 2014 by Ecreall under licence AGPL terms
# available on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

from pyramid.httpexceptions import HTTPFound

from dace.objectofcollaboration.principal.util import get_current
from dace.interfaces import IEntity
from dace.processinstance.activity import InfiniteCardinality

from ..user_management.behaviors import global_user_processsecurity
from novaideo import _


class Nothing(object):
    pass


def close_votes(context, request, vote_processes):
    vote_actions = [process.get_actions('vote')
                    for process in vote_processes]
    vote_actions = [action for actions in vote_actions
                    for action in actions]
    for action in vote_actions:
        action.close_vote(context, request)


def vote_relation_validation(process, context):
    return process.execution_context.has_relation(context, 'subject')


def vote_processsecurity_validation(process, context):
    user = get_current()
    report = process.ballot.report
    elector = report.get_elector(user)
    return elector and not report.he_voted(elector) and \
           global_user_processsecurity()


class VoteBase(InfiniteCardinality):
    title = _('Vote')
    submission_title = _('Save')
    access_controled = True
    context = IEntity
    processs_relation_id = 'subject'
    relation_validation = vote_relation_validation
    processsecurity_validation = vote_processsecurity_validation

    def after_execution(self, context, request, **kw):
        if self.isSequential:
            self.unlock(request)
            self.workitem.unlock(request)

        report = self.process.ballot.report
        if len(report.electors) == len(report.voters):
            self.isexecuted = True
            self.workitem.node.finish_behavior(self.workitem)

    def close_vote(self, context, request, **kw):
        self.workitem.node.finish_behavior(self.workitem)

    def redirect(self, context, request, **kw):
        vote_uid = kw.get('vote_uid', None)
        if vote_uid:
            nothing = Nothing()
            nothing.is_nothing = True
            nothing.vote_uid = vote_uid
            nothing.ballot = kw.get('ballot', None)
            return nothing

        return HTTPFound(request.resource_url(context, '@@index'))
