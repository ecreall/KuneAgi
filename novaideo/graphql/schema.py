# -*- coding: utf-8 -*-
import graphene
from graphene import relay
from graphql_relay.connection.arrayconnection import cursor_to_offset

from hypatia.interfaces import STABLE
from pyramid.threadlocal import get_current_request
from substanced.objectmap import find_objectmap

from dace.util import get_obj, find_catalog

from novaideo.views.filter import find_entities
from novaideo.content.idea import Idea as SDIdea
from novaideo.content.interface import Iidea, IPerson
from novaideo.utilities.util import html_to_text
from novaideo import log


def get_user_by_token(token):
    current_user = None
    novaideo_catalog = find_catalog('novaideo')
    dace_catalog = find_catalog('dace')
    identifier_index = novaideo_catalog['api_token']
    object_provides_index = dace_catalog['object_provides']
    query = object_provides_index.any([IPerson.__identifier__]) &\
        identifier_index.eq(token)
    users = list(query.execute().all())
    return users[0] if users else None


def get_entities(interfaces, states, args, info):  #pylint: disable=W0613
    try:
        after = cursor_to_offset(args.get('after'))
        first = args.get('first')
        if after is None:
            limit = first
        else:
            limit = after + 1 + first

        limit = limit + 1  # retrieve one more so the hasNextPage works
    except Exception:  # FIXME:
        limit = None

    # For the scrolling of the results, it's important that the sort is stable.
    # release_date is set to datetime.datetime.now(tz=pytz.UTC) when the event
    # is published, so we have microsecond resolution and so have a stable sort
    # even with not stable sort algorithms like nbest (because it's unlikely
    # we have several events with the same date).
    # When we specify limit in the query, the sort algorithm chosen will
    # most likely be nbest instead of stable timsort (python sorted).
    # The sort is ascending, meaning we will get new events published during
    # the scroll, it's ok.
    # The only issue we can found here is if x events are removed or unpublished
    # during the scroll, we will skip x new events during the scroll.
    # A naive solution is to implement our own graphql arrayconnection to slice
    # from the last known oid + 1, but the last known oid may not be in the
    # array anymore, so it doesn't work. It's not too bad we skip x events, in
    # reality it should rarely happen.
    rs = find_entities(
        sort_on=None,
        interfaces=interfaces,
        metadata_filter={'states': states},
        text_filter={'text_to_search': args.get('filter', '')}
    )
    catalog = find_catalog('novaideo')
    release_date_index = catalog['release_date']
    return list(release_date_index.sort(
        list(rs.ids), limit=limit, sort_type=STABLE, reverse=True))  #pylint: disable=E1101



class Node(object):

    @classmethod
    def get_node(cls, id, context, info):  #pylint: disable=W0613,W0622
        oid = int(id)
        return get_obj(oid)

    def __getattr__(self, name):
        try:
            return super(Node, self).__getattr__(name)  #pylint: disable=E1101
        except Exception:
            log.exception(
                "Error in node %s id:%s attr:%s",
                self.__class__.__name__, self.id, name)
            raise


class File(Node, graphene.ObjectType):

    class Meta(object):
        interfaces = (relay.Node, )

    url = graphene.String()
    mimetype = graphene.String()


class Person(Node, graphene.ObjectType):

    class Meta(object):
        interfaces = (relay.Node, )

    function = graphene.String()
    description = graphene.String()
    picture = graphene.Field(File)
    first_name = graphene.String()
    last_name = graphene.String()
    title = graphene.String()
    user_title = graphene.String()
    locale = graphene.String()
#    email = graphene.String()
#    email should be visible only by user with Admin or Site Administrator role

    def resolve_picture(self, args, context, info):  #pylint: disable=W0613
        return self.picture


class Idea(Node, graphene.ObjectType):

    """Nova-Ideo ideas."""

    class Meta(object):
        interfaces = (relay.Node, )
   
    created_at = graphene.String()
    state = graphene.List(graphene.String)
    title = graphene.String()
    presentation_text = graphene.String()
    text = graphene.String()
    keywords = graphene.List(graphene.String)
    author = graphene.Field(Person)
    tokens_opposition = graphene.Int()
    tokens_support = graphene.Int()

    @classmethod
    def is_type_of(cls, root, context, info):  #pylint: disable=W0613
        if isinstance(root, cls):
            return True

        return isinstance(root, SDIdea)

    def resolve_created_at(self, args, context, info):
        return self.created_at.isoformat()

    def resolve_presentation_text(self, args, context, info):
        return html_to_text(self.presentation_text(300))

    def resolve_tokens_opposition(self, args, context, info):  #pylint: disable=W0613
        return len(self.tokens_opposition)

    def resolve_tokens_support(self, args, context, info):  #pylint: disable=W0613
        return len(self.tokens_support)


class ResolverLazyList(object):

    def __init__(self, origin, object_type, state=None):
        self._origin = origin
        self._state = state or []
        self._origin_iter = None
        self._finished = False
        objectmap = find_objectmap(get_current_request().root)
        self.resolver = objectmap.object_for
        self.object_type = object_type

    def __iter__(self):
        return self if not self._finished else iter(self._state)

    def iter(self):
        return self.__iter__()

    def __len__(self):
        return self._origin.__len__()

    def __next__(self):
        try:
            if not self._origin_iter:
                self._origin_iter = self._origin.__iter__()
            # n = next(self._origin_iter)
            oid = next(self._origin_iter)
            n = self.resolver(oid)
        except StopIteration as e:
            self._finished = True
            raise e
        else:
            self._state.append(n)
            return n

    def next(self):
        return self.__next__()

    def __getitem__(self, key):
        item = self._origin[key]
        if isinstance(key, slice):
            return self.__class__(item, object_type=self.object_type)

        return item

    def __getattr__(self, name):
        return getattr(self._origin, name)

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, repr(self._origin))


class Query(graphene.ObjectType):

    node = relay.Node.Field()
    ideas = relay.ConnectionField(
        Idea,
        filter=graphene.String()
    )
    account =  graphene.Field(Person)

    def resolve_ideas(self, args, context, info):  #pylint: disable=W0613
        oids = get_entities([Iidea], ['published'], args, info)
        return ResolverLazyList(oids, Idea)

    def resolve_account(self, args, context, info):  #pylint: disable=W0613
        return context.user


schema = graphene.Schema(query=Query)


if __name__ == '__main__':
    import json
    schema_dict = {'data': schema.introspect()}
    with open('schema.json', 'w') as outfile:
        json.dump(schema_dict, outfile)
