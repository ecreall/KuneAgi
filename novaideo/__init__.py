# Copyright (c) 2014 by Ecreall under licence AGPL terms 
# avalaible on http://www.gnu.org/licenses/agpl.html 

# licence: AGPL
# author: Amen Souissi

import logging
from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.i18n import TranslationStringFactory
from pyramid.session import UnencryptedCookieSessionFactoryConfig

from substanced.db import root_factory

from dace.util import getSite

log = logging.getLogger('creationculturelle')

_ = TranslationStringFactory('novaideo')


DEFAULT_SESSION_TIMEOUT = 25200


ACCESS_ACTIONS = {}


def get_access_keys(context):
    declared = context.__provides__.declared
    if declared:
        for data in ACCESS_ACTIONS.get(declared[0], []):
            if data['access_key']:
                return data['access_key'](context)

    return ['always']


def get_novaideo_title():
    return getSite().title


def my_locale_negotiator(request):
    return request.accept_language.best_match(('en', 'fr'), 'fr')


def moderate_ideas(root, registry):
    return getattr(root, 'moderate_ideas', False)


def content_to_examine(root, registry):
    return getattr(root, 'content_to_examine', [])


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings, root_factory=root_factory)
    config.add_request_method(moderate_ideas, reify=True)
    config.add_request_method(content_to_examine, reify=True)
    config.add_translation_dirs('novaideo:locale/')
    config.add_translation_dirs('pontus:locale/')
    config.add_translation_dirs('dace:locale/')
    config.add_translation_dirs('deform:locale/')
    config.add_translation_dirs('colander:locale/')
    config.scan()
    YEAR = 86400 * 365
    config.add_static_view('novaideostatic',
                           'novaideo:static', 
                           cache_max_age=YEAR)
    #    config.set_locale_negotiator(my_locale_negotiator)
    settings = config.registry.settings
    secret = settings.get('novaideo.secret')
    if secret is None:
        raise ConfigurationError(
            'You must set a novaideo.secret key in your .ini file')

    session_factory = UnencryptedCookieSessionFactoryConfig(secret, 
                       timeout=DEFAULT_SESSION_TIMEOUT) 
    config.set_session_factory(session_factory)
    return config.make_wsgi_app()


DEFAULT_FILES = [
    {'name': 'ml_file',
     'title': _('Legal notices'),
     'description': _('The legal notices'),
     'content': ''},
    {'name': 'terms_of_use',
     'title': _('Terms of use'),
     'description': _('The terms of use'),
     'content': ''}
]
