# Copyright (c) 2014 by Ecreall under licence AGPL terms
# avalaible on http://www.gnu.org/licenses/agpl.html

# licence: AGPL
# author: Amen Souissi

import colander
import deform
from zope.interface import implementer, invariant
from persistent.dict import PersistentDict
from persistent.list import PersistentList
from pyramid.threadlocal import get_current_request

from substanced.content import content
from substanced.schema import NameSchemaNode
from substanced.util import renamer, get_oid

from dace.objectofcollaboration.entity import Entity
from dace.descriptors import SharedMultipleProperty, SharedUniqueProperty
from dace.util import get_obj
from pontus.schema import Schema, omit
from pontus.core import VisualisableElement, VisualisableElementSchema
from pontus.widget import (
    Select2Widget,
    SimpleMappingWidget,
    AjaxSelect2Widget)
from deform_treepy.widget import (
    DictSchemaType)

from .interface import ISmartFolder
from novaideo import _, VIEW_TYPES, log
from novaideo.content.person import locale_widget, _LOCALES
from novaideo.views.widget import (
    CssWidget,
    TextInputWidget,
    BootstrapIconInputWidget
    )


DEFAULT_FOLDER_COLORS = {'usual_color': 'white, #2d6ca2',
                         'hover_color': 'white, #2d6ca2'}


def context_is_a_smartfolder(context, request):
    return request.registry.content.istype(context, 'smartfolder')


@colander.deferred
def view_type_widget(node, kw):
    values = list(VIEW_TYPES.items())
    values.insert(0, ('', _('- Select -')))
    return Select2Widget(css_class="viewtype-field",
                         values=values)


class CssSchema(Schema):
    usual_color = colander.SchemaNode(
        colander.String(),
        widget=CssWidget(),
        title=_('Usual color'),
        # description=('Choisir la couleur du texte et du fond de la section de menu.'),
        description=_('Choose the text and background color of the menu section.'),
        )

    hover_color = colander.SchemaNode(
        colander.String(),
        widget=CssWidget(),
        title=_('Hover color'),
        # description=('Choisir la couleur du texte et du fond de la section de menu au survol de la souris.'),
        description=_('Choose the text and background color of the menu section on mouse-over.')
        )


@colander.deferred
def relatedcontents_choice(node, kw):
    request = node.bindings['request']
    context = node.bindings['context']
    root = request.root
    values = []
    if isinstance(context, SmartFolder):
        values = [(get_oid(t), t.title) for
                  t in context.contents]

    def title_getter(id):
        try:
            obj = get_obj(int(id), None)
            if obj:
                return obj.title
            else:
                return id
        except Exception as e:
            log.warning(e)
            return id

    ajax_url = request.resource_url(
        root, '@@novaideoapi',
        query={'op': 'find_smart_folder_contents'})
    return AjaxSelect2Widget(
        values=values,
        ajax_url=ajax_url,
        ajax_item_template="related_item_template",
        title_getter=title_getter,
        multiple=True,
        page_limit=50,)


class SmartFolderSchema(VisualisableElementSchema):
    """Schema for keyword"""

    name = NameSchemaNode(
        editing=context_is_a_smartfolder,
        )

    title = colander.SchemaNode(
        colander.String(),
        widget=TextInputWidget(css_class="smartfolder-title-field"),
        title=_('Title'),
        )

    description = colander.SchemaNode(
        colander.String(),
        widget=deform.widget.TextAreaWidget(rows=4, cols=60),
        title=_("Description"),
        )

    locale = colander.SchemaNode(
        colander.String(),
        title=_('Locale'),
        widget=locale_widget,
        validator=colander.OneOf(_LOCALES),
    )

    contents = colander.SchemaNode(
        colander.Set(),
        widget=relatedcontents_choice,
        title=_('Associated contents'),
        description=_('Choose contents to associate.'),
        missing=[],
        default=[],
        )

    view_type = colander.SchemaNode(
        colander.String(),
        widget=view_type_widget,
        title=_("View type"),
        default='default'
        )

    icon_data = colander.SchemaNode(
        DictSchemaType(),
        widget=BootstrapIconInputWidget(),
        title=_('Icon'),
        default={'icon': 'glyphicon-folder-open',
                 'icon_class': 'glyphicon'},
        description=_('Select an icon.')
        # description="Sélectionner une icône."
        )

    style = omit(CssSchema(widget=SimpleMappingWidget()), ["_csrf_token_"])


@content(
    'smartfolder',
    icon='glyphicon glyphicon-align-left',
    )
@implementer(ISmartFolder)
class SmartFolder(VisualisableElement, Entity):
    """SmartFolder class"""

    default_icon = 'glyphicon glyphicon-folder-open'
    templates = {
        'default': 'novaideo:views/templates/folder_result.pt',
        'bloc': 'novaideo:views/templates/folder_result.pt',
    }
    name = renamer()
    children = SharedMultipleProperty('children', 'parents')
    parents = SharedMultipleProperty('parents', 'children')
    author = SharedUniqueProperty('author', 'folders')
    contents = SharedMultipleProperty('contents')

    def __init__(self, **kwargs):
        super(SmartFolder, self).__init__(**kwargs)
        self.set_data(kwargs)
        self.folder_order = None

    @property
    def parent(self):
        parents = self.parents
        return parents[0] if parents else None

    @property
    def root(self):
        parent = self.parent
        return parent.root if parent else self

    @property
    def folder_lineage(self):
        result = [self]
        parent = self.parent
        if parent:
            parent_result = parent.folder_lineage
            parent_result.extend(result)
            result = parent_result

        return result

    @property
    def icon(self):
        icon = getattr(self, 'icon_data', {})
        if icon:
            return icon.get('icon_class') + ' ' + icon.get('icon')
        else:
            return self.default_icon

    @property
    def url(self,):
        request = get_current_request()
        return self.get_url(request)

    def contains(self, folder):
        if folder is None:
            return False

        if folder is self:
            return True

        return any(c.contains(folder) for c in self.children)

    def all_sub_folders(self, state=None):
        if state:
            result = [f for f in self.children if state in f.state]
        else:
            result = list(self.children)

        for sub_f in list(result):
            result.extend(sub_f.all_sub_folders(state))

        return list(set(result))

    def get_order(self):
        folder_order = getattr(self, 'folder_order', None)
        if folder_order is None:
            root = self.__parent__
            folders = root.smart_folders
            if self in folders:
                self.set_order(folders.index(self))

        return getattr(self, 'folder_order', None)

    def set_order(self, order):
        self.folder_order = order

    def get_url(self, request):
        return request.resource_url(
            request.root, 'open', query={'folderid': get_oid(self)})
