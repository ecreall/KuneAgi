# Copyright (c) 2014 by Ecreall under licence AGPL terms
# avalaible on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

from pyramid.view import view_config

from dace.processinstance.core import DEFAULTMAPPING_ACTIONS_VIEWS
from dace.objectofcollaboration.principal.util import get_current
from pontus.view import BasicView

from novaideo.content.processes.admin_process.behaviors import (
    SeeSmartFolders)
from novaideo.content.novaideo_application import (
    NovaIdeoApplication)
from novaideo import _
from novaideo.views.filter import find_entities
from novaideo.content.interface import ISmartFolder
from novaideo.utilities.util import (
    generate_navbars, render_listing_objs)


CONTENTS_MESSAGES = {
    '0': _(u"""No smart folder found"""),
    '1': _(u"""One smart folder found"""),
    '*': _(u"""${nember} smart folders found""")
}


@view_config(
    name='seesmartfolders',
    context=NovaIdeoApplication,
    renderer='pontus:templates/views_templates/grid.pt',
    )
class SeeSmartFoldersView(BasicView):
    title = ''
    name = 'seesmartfolders'
    behaviors = [SeeSmartFolders]
    template = 'novaideo:views/admin_process/templates/see_smartfolders.pt'
    viewid = 'seesmartfolders'

    def update(self):
        self.execute(None)
        user = get_current()
        folders = find_entities(
            user=user,
            interfaces=[ISmartFolder])
        folders = [sf for sf in folders if not sf.parents]
        folders = sorted(folders, key=lambda e: e.get_order())
        root_navbars = generate_navbars(
            self.request, self.context,
            process_id='adminprocess',
            descriminators=['body-action'])
        len_result = len(folders)
        index = str(len_result)
        if len_result > 1:
            index = '*'

        self.title = _(CONTENTS_MESSAGES[index],
                       mapping={'nember': len_result})
        result_body, result = render_listing_objs(
            self.request, folders, user)
        values = {
            'folders': result_body,
            'body_actions': root_navbars['body_actions']
        }
        body = self.content(args=values, template=self.template)['body']
        item = self.adapt_item(body, self.viewid)
        result['coordinates'] = {self.coordinates: [item]}
        return result


DEFAULTMAPPING_ACTIONS_VIEWS.update({SeeSmartFolders: SeeSmartFoldersView})