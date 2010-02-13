from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template

import logging
import models
import os

class BaseHandler(webapp.RequestHandler):
    """Base handler, provides render_to_response with default parameters"""

    template_dir = os.path.join(os.path.dirname(__file__), 'templates')

    def render_to_response(self, template_name='index', values = {}, format='html'):
        values.update({
            'settings': models.Setting.get_dictionary()
        })

        if format == 'feed':
            template_name = 'atom'
            self.response.content_type = 'application/atom+xml; charset=utf-8'
        elif not format:
            format = 'html'

        # App engine uses text/html and utf-8 by default
        # http://code.google.com/appengine/docs/python/tools/webapp/buildingtheresponse.html

        template_path = os.path.join(self.template_dir, template_name + '.' + format)

        self.response.out.write(template.render(template_path, values))

class SlashRedirectHandler(webapp.RequestHandler):
    """Strip off slashes and permanent redirect to the slashless path"""
    def get(self, path):
        self.redirect(path, permanent=True)

class DateHandler(webapp.RequestHandler):
    """Redirect to the main archive page, with a hash for the year and month"""
    def get(self, year, month=None):
        url = '/archive#y-' + year
        if month:
            url += '-m-%s' % int(month)

        self.redirect(url)

class SiteHandler(BaseHandler):
    """Handle the audience-facing side of the site"""

    def get(self, slug):
        item = models.Item.get_by_slug(slug)
        if not item:
            return self.redirect_or_404(slug)

        self.render_to_response('item', {
            'item': item,
            'title': item.title
        })

    def redirect_or_404(self, slug):
        """Find out if the slug was previously used. If so, redirect. Otherwise, 404"""
        alias = models.Alias.get_by_slug(slug)
        if alias and alias.item.is_published:
            self.redirect(alias.item.slug, permanent=True)
        else:
            self.error(404)
            self.render_to_response('404', {
                'path': slug,
                'title': "Not Found"
            })

class RootHandler(SiteHandler):
    """Special case for the root element"""
    def get(self, archive=False, format='html'):
        root = models.Item.get_by_slug('/')
        posts = models.Item.all_published_posts()

        if not archive:
            # Limit number of front page posts
            posts = posts.fetch(10)

        # Get settings
        settings = models.Setting.get_dictionary()

        # Only give feedburner access to the feed, all others get
        # redirected
        if format == 'feed' and settings['feedburner_address']:
            userAgent = self.request.headers.get('User-Agent', '')
            if not 'feedburner' in userAgent:
                return self.redirect(settings['feedburner_address'])

        self.render_to_response('base', {
            'item': root,
            'posts': posts,
            'title': settings['site_title'],
            'archive': archive,
        }, format)

class AdminBaseHandler(BaseHandler):
    # Admin templates live in a different directory
    template_dir = os.path.join(BaseHandler.template_dir, 'admin')

    def render_to_response(self, template_name='index',
                           values={}, format='html'):
        values.update({
            'user': users.get_current_user(),
            'logout_url': users.create_logout_url('/admin')
        })
        BaseHandler.render_to_response(self, template_name, values, format)

    def get(self):
        # Get all entries
        items = models.Item.all().order('-publish_date')

        # No items means we haven't been set up properly
        if not items.count(1):
            return self.redirect('/admin/settings')

        # Render
        self.render_to_response('index', {
            'items': items,
            'title': 'Admin Home'
        })

    def post(self):
        if self.request.get('delete'):
            item = models.Item.get_by_id(int(self.request.get('delete')))
            if not item.is_trash:
                item.trash()
            else:
                item.purge()
        elif self.request.get('edit'):
            self.redirect('/admin/item/%s' % self.request.get('edit'))
            return
        elif self.request.get('new'):
            self.redirect('/admin/item')
            return

        # Redirect to GET
        self.redirect('/admin')


class ItemHandler(AdminBaseHandler):
    def get(self, item_id=None):
        """Show editing UI for an item"""
        item = models.Item()
        item.title = "New Post"
        if item_id:
            # Fetch item if it exists
            item = models.Item.get_by_id(int(item_id))

        self.render_to_response('item', {
            'item': item,
            'title': 'Edit: %s' % item.title
        })

    def post(self, item_id=None):
        item = models.Item()
        if item_id:
            item = models.Item.get_by_id(int(item_id))

        if self.request.get('action') == 'Delete':
            if not item.is_trash:
                item.trash()
            else:
                item.purge()
        else:
            # Check for published button
            if self.request.get('action') == 'Publish':
                # Could get overriden by content ...
                item.status = models.Item.PUBLISHED

            item.update_content(self.request.get('content'))
            item.save()

        # Keep editing on save
        if self.request.get('action') == 'Save' and item_id:
            self.redirect('/admin/item/%s' % item_id)
        else:
            # Otherwise, redirect back to main
            self.redirect('/admin')


class SettingsHandler(AdminBaseHandler):
    STANDARD_SETTINGS = [
        'author_name', 'site_title', 'site_blurb', 'site_host', 'advanced_mode',
        'google_profile', 'feedburner_address', 'google_analytics'
    ]
    """Handler for settings viewing and deletion"""
    def get(self):
        """Display current settings with editing form"""
        self.render_to_response('settings', {
            # Get fresh (non-memcache) results
            'settings_list': models.Setting.all(),
            'title': 'Settings'
        })

    def post(self):
        """Process setting creation, editing, and deletion

        When finished, flushes memcache settings and redirects to GET
        """
        if self.request.get('save_changes'):
            # Save normal settings
            settings = []
            for name in self.STANDARD_SETTINGS:
                setting = models.Setting.get_or_insert(name, name=name)
                setting.value = self.request.get(name)
                settings.append(setting)

            # Bulk save
            db.put(settings)

        if self.request.get('delete'):
            name = self.request.get('delete')
            if name:
                db.delete(models.Setting.get_by_key_name(name))
        else:
            if self.request.get('save'):
                name = self.request.get('save')
                value = self.request.get(name)
                logging.info('Updated setting %s' % name)
            elif self.request.get('create'):
                name = self.request.get('create_name')
                value = self.request.get('create_value')
                logging.info('Created new setting %s' % name)
            else:
                name = None
                logging.error('Stray POST to /admin/settings')

            if name:
                setting = models.Setting.get_or_insert(name, name=name)
                setting.value = value
                setting.put()

        # Clear cache and redirect to GET
        models.Setting.flush_cache()

        # Make sure we have a root page
        if not models.Item.get_by_slug('/'):
            self.create_root_page()

        self.redirect('/admin/settings')

    def create_root_page(self):
        root = models.Item()
        root.slug = '/'
        root.is_post = False
        root.title = models.Setting.get_dictionary()['site_title']
        root.status = models.Item.PUBLISHED
        root.put()
