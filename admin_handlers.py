from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext.webapp import template

import logging
import models
import handlers # BaseHandler
import os

class AdminBaseHandler(handlers.BaseHandler):
    # Admin templates live in a different directory
    template_dir = os.path.join(handlers.BaseHandler.template_dir, 'admin')

    def render_template_to_response(self, template_name='index',
                           values={}, format='html'):
        values.update({
            'user': users.get_current_user(),
            'logout_url': users.create_logout_url('/admin')
        })
        handlers.BaseHandler.render_template_to_response(self, template_name, values, format)

    def get(self):
        # Get all entries
        items = models.Item.all().order('-publish_date')

        # No items means we haven't been set up properly
        if not items.count(1):
            return self.redirect('/admin/settings')

        # Render
        self.render_template_to_response('index', {
            'items': items,
            'title': 'Admin Home'
        })

    def post(self):
        if self.request.get('edit'):
            self.redirect('/admin/item/%s' % self.request.get('edit'))
            return
        elif self.request.get('new'):
            self.redirect('/admin/item')
            return
        elif self.request.get('delete'):
            item = models.Item.get_by_id(int(self.request.get('delete')))
            if not item.is_trash:
                item.trash()
            else:
                item.purge()

        # Flush cache for changes
        self.flush_root_cache()

        # Redirect to GET
        self.redirect('/admin')

    def flush_root_cache(self):
        memcache.delete_multi(['root_html', 'archive_html'])


class ItemHandler(AdminBaseHandler):
    def get(self, item_id=None):
        """Show editing UI for an item"""
        item = models.Item()
        if item_id:
            # Fetch item if it exists
            item = models.Item.get_by_id(int(item_id))
        else:
            item.title = "New Post"

        self.render_template_to_response('item', {
            'item': item,
            'title': 'Edit: %s' % item.title
        })

    def post(self, item_id=None):
        item = models.Item()
        if item_id:
            item = models.Item.get_by_id(int(item_id))

        # Check for published button
        if self.request.get('action') == 'Publish':
            item.status = models.Item.PUBLISHED

        item.update_content(self.request.get('content'))
        item.save()
        self.flush_root_cache()

        # Keep editing on save
        if self.request.get('action') == 'Save':
            # New entry has a new id
            if not item_id:
                item_id = item.key().id()

            self.redirect('/admin/item/%s' % item_id)
        else:
            self.redirect('/admin')


class SettingsHandler(AdminBaseHandler):
    STANDARD_SETTINGS = [
        'author_name', 'site_title', 'site_blurb', 'site_host', 'advanced_mode',
        'google_profile', 'feedburner_address', 'google_analytics'
    ]
    """Handler for settings viewing and deletion"""
    def get(self):
        """Display current settings with editing form"""
        self.render_template_to_response('settings', {
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

        # Make sure we have a root page
        if not models.Item.get_by_slug('/'):
            self.create_root_page()

        # Refresh cache and redirect to GET
        models.Setting.refresh_cache()
        self.flush_root_cache()
        self.redirect('/admin/settings')

    def create_root_page(self):
        root = models.Item()
        root.slug = '/'
        root.is_post = False
        root.title = models.Setting.get_dictionary()['site_title']
        root.status = models.Item.PUBLISHED
        root.put()
