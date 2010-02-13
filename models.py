from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import memcache

import logging
import datetime
from lib import helpers

class Setting(db.Model):
    """Model for storing strings used in application"""
    name = db.StringProperty(indexed=True, required=True)
    value = db.StringProperty(indexed=False)

    @classmethod
    def get_dictionary(klass):
        """Returns a dictionary with all stored settings. Uses memcache"""
        # Cache due to frequent access
        settings = memcache.get('settings')

        if not settings:
            logging.info('Settings cache miss')
            settings = klass.refresh_cache()

        return settings

    @classmethod
    def refresh_cache(klass):
        """Replace stored settings from memcache. Must be called whenever
        a settings value is changed
        """
        settings = dict([(s.name, s.value) for s in klass.all()])
        memcache.replace('settings', settings)
        return settings


class Item(db.Expando):
    """Model for all content"""
    # Status
    DRAFT, PUBLISHED, TRASH = range(3)

    # Model definition
    slug = db.StringProperty(indexed=True)
    title = db.StringProperty(indexed=False)
    content = db.TextProperty()
    # HTML generated from markdown content
    content_html = db.TextProperty()
    status = db.IntegerProperty(indexed=True, default=DRAFT, choices=range(3))
    publish_date = db.DateTimeProperty(indexed=True, auto_now_add=True, verbose_name='Publish date')
    updated_date = db.DateTimeProperty(auto_now=True, verbose_name='Last updated date')
    is_post = db.BooleanProperty(indexed=True, default=True)

    # Status helper properties
    @property
    def is_draft(self):
        return self.status == self.DRAFT

    @property
    def is_published(self):
        return self.status == self.PUBLISHED and self.publish_date <= datetime.datetime.now()

    @property
    def is_future(self):
        return self.status == self.PUBLISHED and not self.is_published

    @property
    def is_trash(self):
        return self.status == self.TRASH

    @property
    def verbose_status(self):
        """Human-readable status"""
        if self.status == self.DRAFT:
            return 'Draft'
        elif self.status == self.PUBLISHED:
            return 'Published'
        else:
            return 'Trash'

    # Query helpers
    @classmethod
    def all_published(klass):
        """All items with status published and a publish date in the past"""
        return klass.all().filter('status', klass.PUBLISHED)\
                .filter('publish_date <=', datetime.datetime.now())

    @classmethod
    def all_published_posts(klass):
        """Only published items that are not pages/tags"""
        return klass.all_published().filter('is_post', True).order('-publish_date')

    @classmethod
    def get_by_slug(klass, slug):
        return klass.all_published().filter('slug', slug).get()

    # Slug helper properties
    @property
    def is_root(self):
        return self.slug == '/'

    @property
    def archive_link(self):
        if self.is_root:
            return '/archive'
        else:
            return '%s/archive' % self.slug

    # Field extraction means content updating isn't straightforward
    def update_content(self, content):
        if (content == self.content):
            pass # return

        # Store
        self.content = content

        # Extract fields and convert to html
        self.content_html, data = helpers.process_content(content, self.publish_date)

        # Assign extracted data if there
        if 'date' in data:
            self.publish_date = data['date']
        if 'title' in data:
            self.title = data['title']
        if 'slug' in data:
            self.slug = data['slug']
        if 'page' in data:
            self.is_post = False

    # Datastore interaction helpers
    def save(self):
        """Save item to the datastore"""
        # Do validation?
        if self.is_root:
            self.is_post = False

        # Todo: Error-check
        self.put()

        # Map Aliases for published posts
        if self.is_published:
            Alias.add_alias(self, self.slug)

    def trash(self, auto_put=True):
        """Put the item in the trash"""
        self.status = self.TRASH
        # Caller may wish to do a bulk put
        if auto_put:
            self.put()

    def purge(self, auto_delete=True):
        """Delete the item from the datastore and remove all aliases"""
        db.delete(self.aliases)
        # Caller may wish to run a single db.delete() call in bulk
        if auto_delete:
            self.delete()


class Alias(db.Model):
    """Stores previously-used slugs for redirection of items"""
    # Use key_name for all lookups
    item = db.ReferenceProperty(reference_class=Item, collection_name='aliases')

    # Static helpers
    @classmethod
    def get_by_slug(klass, slug):
        """Get an alias by it's slug"""
        return klass.get_by_key_name(slug)

    @classmethod
    def add_alias(klass, item, slug):
        """Register an alias for a item"""
        if (item.slug):
            alias = klass.get_or_insert(item.slug, item=item)
            alias.item = item
            alias.put()
