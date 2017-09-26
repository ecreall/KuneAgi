import graphene
import urllib
from pyramid.threadlocal import get_current_request

from pontus.schema import select
from dace.objectofcollaboration.principal.util import has_role
from dace.util import get_obj, find_catalog, getSite, getAllBusinessAction
from pontus.file import File

from novaideo.content.interface import IPerson
from novaideo.content.idea import Idea as IdeaClass, IdeaSchema

def get_context(oid):
    try:
        return get_obj(int(oid))
    except:
        return getSite()


def get_action(action_id, context, request):
    node_process = action_id.split('.')
    if len(node_process) == 2:
        process_id, node_id = node_process
        node_actions = getAllBusinessAction(
            context, request,
            process_id=process_id, node_id=node_id,
            process_discriminator='Application')
        if node_actions:
            return node_actions[0]

    return None


def get_execution_data(action_id, args):
    context = get_context(
        args.pop('context') if 'context' in args else None)
    request = get_current_request()
    action = get_action(action_id, context, request)
    return context, request, action, args


class Upload(graphene.InputObjectType):
    name = graphene.String()
    type = graphene.String()
    uri = graphene.String()


class CreateIdea(graphene.Mutation):

    class Input:
        title = graphene.String()
        text = graphene.String()
        keywords = graphene.List(graphene.String)
        attached_files = graphene.List(Upload)

    status = graphene.Boolean()
    idea = graphene.Field('novaideo.graphql.schema.Idea')
    action_id = 'ideamanagement.creat'

    @staticmethod
    def mutate(root, args, context, info):
        idea_schema = select(
            IdeaSchema(), ['title', 'text', 'keywords', 'attached_files'])
        args = dict(args)
        attached_files = args.pop('attached_files', None)
        uploaded_files = []
        if attached_files:
            for index, file_ in enumerate(attached_files):
                file_storage = context.POST.get(
                    'variables.attachedFiles.'+str(index))
                fp = file_storage.file
                fp.seek(0)
                uploaded_files.append({
                    'fp': fp,
                    'filename': urllib.parse.unquote(file_storage.filename)})

        args['attached_files'] = uploaded_files
        args = idea_schema.deserialize(args)
        args['attached_files'] = [f['_object_data']
                                  for f in args['attached_files']]
        context, request, action, args = get_execution_data(
            CreateIdea.action_id, args)
        new_idea = None
        if action:
            new_idea = IdeaClass(**args)
            appstruct = {
                '_object_data': new_idea
            }
            action.execute(context, request, appstruct)
        else:
            raise Exception("Authorization failed")

        status = new_idea is not None
        return CreateIdea(idea=new_idea, status=status)


class CreateAndPublishIdea(graphene.Mutation):

    class Input:
        title = graphene.String()
        text = graphene.String()
        keywords = graphene.List(graphene.String)
        attached_files = graphene.List(Upload) # this is the identifiers of the part in a multipart POST

    status = graphene.Boolean()
    idea = graphene.Field('novaideo.graphql.schema.Idea')
    action_id = 'ideamanagement.creatandpublish'

    @staticmethod
    def mutate(root, args, context, info):
        idea_schema = select(
            IdeaSchema(), ['title', 'text', 'keywords', 'attached_files'])
        args = dict(args)
        attached_files = args.pop('attached_files', None)
        uploaded_files = []
        if attached_files:
            for index, file_ in enumerate(attached_files):
                file_storage = context.POST.get(
                    'variables.attachedFiles.'+str(index))
                fp = file_storage.file
                fp.seek(0)
                uploaded_files.append({
                    'fp': fp,
                    'filename': urllib.parse.unquote(file_storage.filename)})

        args['attached_files'] = uploaded_files
        args = idea_schema.deserialize(args)
        args['attached_files'] = [f['_object_data']
                                  for f in args['attached_files']]
        context, request, action, args = get_execution_data(
            CreateAndPublishIdea.action_id, args)
        new_idea = None
        if action:
            new_idea = IdeaClass(**args)
            appstruct = {
                '_object_data': new_idea
            }
            action.execute(context, request, appstruct)
        else:
            raise Exception("Authorization failed")

        status = new_idea is not None
        return CreateAndPublishIdea(idea=new_idea, status=status)

class Mutations(graphene.ObjectType):
    create_idea = CreateIdea.Field()
    create_and_publish = CreateAndPublishIdea.Field()
