# -*- coding: utf-8 -*-
#
# gPodder - A media aggregator and podcast client
# Copyright (c) 2005-2018 The gPodder Team
#
# gPodder is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# gPodder is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import gi

gi.require_version('Gtk', '3.0')  # isort:skip
gi.require_version('Gdk', '3.0')  # isort:skip
gi.require_version('Handy', '1')  # isort:skip
from gi.repository import Gdk, Gtk, Handy, Pango

import gpodder
from gpodder import util
from gpodder.gtkui.interface.common import BuilderWidget, TreeViewHelper
from gpodder.gtkui.model import GEpisode

from .. import shownotes

_ = gpodder.gettext
N_ = gpodder.ngettext


class gPodderEpisodeSelector(BuilderWidget):
    """Episode selection dialog

    Optional keyword arguments that modify the behaviour of this dialog:

      - callback: Function that takes 1 parameter which is a list of
                  the selected episodes (or empty list when none selected)
      - remove_callback: Function that takes 1 parameter which is a list
                         of episodes that should be "removed" (see below)
                         (default is None, which means remove not possible)
      - remove_action: Label for the "remove" action (default is "Remove")
      - remove_finished: Callback after all remove callbacks have finished
                         (default is None, also depends on remove_callback)
                         It will get a list of episode URLs that have been
                         removed, so the main UI can update those
      - episodes: List of episodes that are presented for selection
      - selected: (optional) List of boolean variables that define the
                  default checked state for the given episodes
      - selected_default: (optional) The default boolean value for the
                          checked state if no other value is set
                          (default is False)
      - columns: List of (name, sort_name, sort_type, caption) pairs for the
                 columns, the name is the attribute name of the episode to be
                 read from each episode object.  The sort name is the
                 attribute name of the episode to be used to sort this column.
                 If the sort_name is None it will use the attribute name for
                 sorting.  The sort type is the type of the sort column.
                 The caption attribute is the text that appear as column caption
                 (default is [('title_markup', None, None, 'Episode'),])
      - title: (optional) The title of the window + heading
      - instructions: (optional) A one-line text describing what the
                      user should select / what the selection is for
      - ok_button: (optional) Will replace the "OK" button label with this
                   string (e.g. can be '_Delete' when the episodes to be
                   selected will be deleted after closing the dialog)
      - selection_buttons: (optional) A dictionary with labels as
                           keys and callbacks as values; for each
                           key a button will be generated, and when
                           the button is clicked, the callback will
                           be called for each episode and the return
                           value of the callback (True or False) will
                           be the new selected state of the episode
      - size_attribute: (optional) The name of an attribute of the
                        supplied episode objects that can be used to
                        calculate the size of an episode; set this to
                        None if no total size calculation should be
                        done (in cases where total size is useless)
                        (default is 'file_size')
      - tooltip_attribute: (optional) The name of an attribute of
                           the supplied episode objects that holds
                           the text for the tooltips when hovering
                           over an episode (default is 'description')
      - gPodder: Main gPodder instance
    """
    COLUMN_INDEX = 0
    COLUMN_TOOLTIP = 1
    COLUMN_TOGGLE = 2
    COLUMN_ADDITIONAL = 3

    def new(self):
        # self.gPodderEpisodeSelector.set_transient_for(self.parent_widget)
        if hasattr(self, 'title'):
            self.gPodderEpisodeSelector.set_title(self.title)

        self._config.connect_gtk_window(self.gPodderEpisodeSelector, 'episode_selector', True)

        if not hasattr(self, 'callback'):
            self.callback = None

        if not hasattr(self, 'remove_callback'):
            self.remove_callback = None

        if not hasattr(self, 'remove_action'):
            self.remove_action = _('Remove')

        if not hasattr(self, 'remove_finished'):
            self.remove_finished = None

        if not hasattr(self, 'episodes'):
            self.episodes = []

        if not hasattr(self, 'size_attribute'):
            self.size_attribute = 'file_size'

        if not hasattr(self, 'tooltip_attribute'):
            self.tooltip_attribute = '_text_description'

        if not hasattr(self, 'selection_buttons'):
            self.selection_buttons = {}

        if not hasattr(self, 'selected_default'):
            self.selected_default = False

        if not hasattr(self, 'selected'):
            self.selected = [self.selected_default] * len(self.episodes)

        if len(self.selected) < len(self.episodes):
            self.selected += [self.selected_default] * (len(self.episodes) - len(self.selected))

        if not hasattr(self, 'columns'):
            self.columns = (('title_markup', None, None, _('Episode')),)

        if hasattr(self, 'instructions'):
            self.labelInstructions.set_text(self.instructions)
            self.labelInstructions.show_all()

        if hasattr(self, 'ok_button'):
            if self.ok_button == 'gpodder-download':
                self.btnOK.set_image(Gtk.Image.new_from_icon_name('go-down', Gtk.IconSize.BUTTON))
                self.btnOK.set_label(_('_Download'))
            else:
                self.btnOK.set_image(None)
                self.btnOK.set_label(self.ok_button)

        # check/uncheck column
        toggle_cell = Gtk.CellRendererToggle()
        toggle_cell.set_fixed_size(48, -1)
        toggle_cell.connect('toggled', self.toggle_cell_handler)
        toggle_column = Gtk.TreeViewColumn('', toggle_cell, active=self.COLUMN_TOGGLE)
        toggle_column.set_clickable(True)
        self.treeviewEpisodes.append_column(toggle_column)

        self.toggled = False

        next_column = self.COLUMN_ADDITIONAL
        for name, sort_name, sort_type, caption in self.columns:
            renderer = Gtk.CellRendererText()
            if next_column < self.COLUMN_ADDITIONAL + 1:
                renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
            column = Gtk.TreeViewColumn(caption, renderer, markup=next_column)
            column.set_clickable(False)
            column.set_resizable(True)
            # Only set "expand" on the first column
            if next_column < self.COLUMN_ADDITIONAL + 1:
                column.set_expand(True)
            if sort_name is not None:
                column.set_sort_column_id(next_column + 1)
            else:
                column.set_sort_column_id(next_column)
            self.treeviewEpisodes.append_column(column)
            next_column += 1

            if sort_name is not None:
                # add the sort column
                column = Gtk.TreeViewColumn()
                column.set_clickable(False)
                column.set_visible(False)
                self.treeviewEpisodes.append_column(column)
                next_column += 1

        column_types = [int, str, bool]
        # add string column type plus sort column type if it exists
        for name, sort_name, sort_type, caption in self.columns:
            column_types.append(str)
            if sort_name is not None:
                column_types.append(sort_type)
        self.model = Gtk.ListStore(*column_types)

        tooltip = None
        for index, episode in enumerate(self.episodes):
            if self.tooltip_attribute is not None:
                try:
                    tooltip = getattr(episode, self.tooltip_attribute)
                except:
                    tooltip = None
            row = [index, tooltip, self.selected[index]]
            for name, sort_name, sort_type, caption in self.columns:
                if not hasattr(episode, name):
                    row.append(None)
                else:
                    row.append(getattr(episode, name))

                if sort_name is not None:
                    if not hasattr(episode, sort_name):
                        row.append(None)
                    else:
                        row.append(getattr(episode, sort_name))
            self.model.append(row)

        if self.remove_callback is not None:
            self.btnRemoveAction.show()
            self.btnRemoveAction.set_label(self.remove_action)

        # connect to tooltip signals
        if self.tooltip_attribute is not None:
            try:
                self.treeviewEpisodes.set_property('has-tooltip', True)
                self.treeviewEpisodes.connect('query-tooltip', self.treeview_episodes_query_tooltip)
            except:
                pass
        self.last_tooltip_episode = None
        self.episode_list_can_tooltip = True

        # Keyboard shortcuts
        def on_key_press_episodes(widget, event):
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
                return False
            elif event.keyval == Gdk.KEY_a:
                self.btnCheckAll.emit("clicked")
            elif event.keyval == Gdk.KEY_n:
                self.btnCheckNone.emit("clicked")
            elif event.keyval in (Gdk.KEY_Escape, Gdk.KEY_BackSpace):
                self.btnCancel.emit("clicked")
            elif event.keyval in (Gdk.KEY_Right, Gdk.KEY_l):
                self.toggled = False
                path, column = self.treeviewEpisodes.get_cursor()
                self.on_row_activated(self.treeviewEpisodes, path, column)
            elif event.keyval in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_j, Gdk.KEY_k):
                path, column = self.treeviewEpisodes.get_cursor()
                step = -1 if event.keyval in (Gdk.KEY_Up, Gdk.KEY_k) else 1
                model = self.treeviewEpisodes.get_model()
                if path is None:
                    if model is None or model.get_iter_first() is None:
                        return True
                    else:
                        path = (0,)
                else:
                    path = (path[0] + step,)
                if path[0] < 0:
                    return True
                try:
                    it = model.get_iter(path)
                except ValueError:
                    return True
                self.treeviewEpisodes.set_cursor(path, toggle_column)
            else:
                return False
            return True

        # Consume arrow keys before native TreeView keyboard handlers
        def on_key_press_treeview(widget, event):
            if event.keyval in (Gdk.KEY_Right, Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_Down):
                return on_key_press_episodes(widget, event)
            return False

        self.new_episodes_box.connect('key-press-event', on_key_press_episodes)
        self.treeviewEpisodes.connect('key-press-event', on_key_press_treeview)

        def on_key_press_shownotes(widget, event):
            if event.keyval in (Gdk.KEY_Escape, Gdk.KEY_BackSpace, Gdk.KEY_Left, Gdk.KEY_h):
                self.new_deck.navigate(Handy.NavigationDirection.BACK)
                self.treeviewEpisodes.grab_focus()
            elif event.keyval in (Gdk.KEY_s, Gdk.KEY_p):
                self.stream_button.emit("clicked")
            else:
                return False
            return True

        self.detailsbox.connect('key-press-event', on_key_press_shownotes)

        self.treeviewEpisodes.connect('button-press-event', self.treeview_episodes_button_pressed)
        self.treeviewEpisodes.connect('popup-menu', self.treeview_episodes_button_pressed)
        self.treeviewEpisodes.set_rules_hint(True)
        self.treeviewEpisodes.set_model(self.model)
        self.treeviewEpisodes.columns_autosize()

        TreeViewHelper.set_cursor_to_first(self.treeviewEpisodes)
        # Focus the toggle column for Tab-focusing (bug 503)
        path, column = self.treeviewEpisodes.get_cursor()
        if path is not None:
            self.treeviewEpisodes.set_cursor(path, toggle_column)

        # self.shownotes_object = shownotes.get_shownotes(self._config.ui.gtk.html_shownotes, self.shownotes_box)
        # Hardcode non-HTML shownotes because of webkit2gtk crashing with multiple instances
        self.shownotes_object = shownotes.get_shownotes(False, self.shownotes_box)

        self.activated_episode = None

        self.calculate_total_size()

    def treeview_episodes_query_tooltip(self, treeview, x, y, keyboard_tooltip, tooltip):
        # With get_bin_window, we get the window that contains the rows without
        # the header. The Y coordinate of this window will be the height of the
        # treeview header. This is the amount we have to subtract from the
        # event's Y coordinate to get the coordinate to pass to get_path_at_pos
        (x_bin, y_bin) = treeview.get_bin_window().get_position()
        y -= x_bin
        y -= y_bin
        (path, column, rx, ry) = treeview.get_path_at_pos(x, y) or (None,) * 4

        if not self.episode_list_can_tooltip or column != treeview.get_columns()[1]:
            self.last_tooltip_episode = None
            return False

        if path is not None:
            model = treeview.get_model()
            iter = model.get_iter(path)
            index = model.get_value(iter, self.COLUMN_INDEX)
            description = model.get_value(iter, self.COLUMN_TOOLTIP)
            if self.last_tooltip_episode is not None and self.last_tooltip_episode != index:
                self.last_tooltip_episode = None
                return False
            self.last_tooltip_episode = index

            description = util.remove_html_tags(description)
            # Bug 1825: make sure description is a unicode string,
            # so it may be cut correctly on UTF-8 char boundaries
            description = util.convert_bytes(description)
            if description is not None:
                if len(description) > 400:
                    description = description[:398] + '[...]'
                tooltip.set_text(description)
                return True
            else:
                return False

        self.last_tooltip_episode = None
        return False

    def treeview_episodes_button_pressed(self, treeview, event=None):
        pass
#        if event is None or event.triggers_context_menu():
#            menu = Gtk.Menu()
#
#            if len(self.selection_buttons):
#                for label in self.selection_buttons:
#                    item = Gtk.MenuItem(label)
#                    item.connect('activate', self.custom_selection_button_clicked, label)
#                    menu.append(item)
#                menu.append(Gtk.SeparatorMenuItem())
#
#            item = Gtk.MenuItem(_('Select all'))
#            item.connect('activate', self.on_btnCheckAll_clicked)
#            menu.append(item)
#
#            item = Gtk.MenuItem(_('Select none'))
#            item.connect('activate', self.on_btnCheckNone_clicked)
#            menu.append(item)
#
#            menu.show_all()
#            # Disable tooltips while we are showing the menu, so
#            # the tooltip will not appear over the menu
#            self.episode_list_can_tooltip = False
#            menu.connect('deactivate', lambda menushell: self.episode_list_allow_tooltips())
#            if event is None:
#                func = TreeViewHelper.make_popup_position_func(treeview)
#                menu.popup(None, None, func, None, 3, Gtk.get_current_event_time())
#            else:
#                menu.popup(None, None, None, None, event.button, event.time)
#
#            return True

    def episode_list_allow_tooltips(self):
        self.episode_list_can_tooltip = True

    def calculate_total_size(self):
        if self.size_attribute is not None:
            (total_size, count) = (0, 0)
            for episode in self.get_selected_episodes():
                try:
                    total_size += int(getattr(episode, self.size_attribute))
                    count += 1
                except:
                    pass

            text = []
            if count == 0:
                text.append(_('Nothing selected'))
            text.append(N_('%(count)d episode', '%(count)d episodes',
                           count) % {'count': count})
            if total_size > 0:
                text.append(_('size: %s') % util.format_filesize(total_size))
            self.labelTotalSize.set_text(', '.join(text))
            self.btnOK.set_sensitive(count > 0)
            self.btnRemoveAction.set_sensitive(count > 0)
            if count > 0:
                self.btnCancel.set_label(_('_Cancel'))
            else:
                self.btnCancel.set_label(_('_Close'))
        else:
            self.btnOK.set_sensitive(False)
            self.btnRemoveAction.set_sensitive(False)
            for index, row in enumerate(self.model):
                if self.model.get_value(row.iter, self.COLUMN_TOGGLE) is True:
                    self.btnOK.set_sensitive(True)
                    self.btnRemoveAction.set_sensitive(True)
                    break
            self.labelTotalSize.set_text('')

    def toggle_cell_handler(self, cell, path):
        model = self.treeviewEpisodes.get_model()
        model[path][self.COLUMN_TOGGLE] = not model[path][self.COLUMN_TOGGLE]
        self.toggled = True
        self.calculate_total_size()

    def custom_selection_button_clicked(self, button, label):
        callback = self.selection_buttons[label]

        for index, row in enumerate(self.model):
            new_value = callback(self.episodes[index])
            self.model.set_value(row.iter, self.COLUMN_TOGGLE, new_value)

        self.calculate_total_size()

    def on_btnCheckAll_clicked(self, widget):
        for row in self.model:
            self.model.set_value(row.iter, self.COLUMN_TOGGLE, True)

        self.calculate_total_size()

    def on_btnCheckNone_clicked(self, widget):
        for row in self.model:
            self.model.set_value(row.iter, self.COLUMN_TOGGLE, False)

        self.calculate_total_size()

    def on_remove_action_activate(self, widget):
        episodes = self.get_selected_episodes(remove_episodes=True)

        urls = []
        for episode in episodes:
            urls.append(episode.url)
            self.remove_callback(episode)

        if self.remove_finished is not None:
            self.remove_finished(urls)
        self.calculate_total_size()

        # Close the window when there are no episodes left
        model = self.treeviewEpisodes.get_model()
        if model.get_iter_first() is None:
            self.on_btnCancel_clicked(None)

    def on_stream_button_clicked(self, *args):
        if hasattr(self, 'gPodder') and self.activated_episode is not None:
            self.gPodder.playback_episodes((self.activated_episode,))

    def on_row_activated(self, treeview, path, view_column):
        if self.toggled:
            self.toggled = False
            return True
        model = treeview.get_model()
        itr = model.get_iter(path)
        epind = model.get_value(itr, 0)
        episodes = [self.episodes[epind]]
        assert episodes
        if isinstance(episodes[0], GEpisode):  # No notes for channels
            self.activated_episode = episodes[0]
            if episodes[0].can_stream(self._config) and hasattr(self, 'gPodder'):
                self.stream_button.set_sensitive(True)
            else:
                self.stream_button.set_sensitive(False)
            self.shownotes_object.show_pane(episodes)
            self.shownotes_box.show()
            self.new_deck.set_can_swipe_forward(True)
            self.notes_back.grab_focus()
            self.new_deck.navigate(Handy.NavigationDirection.FORWARD)
        else:
            self.activated_episode = None

        self.calculate_total_size()

    def get_selected_episodes(self, remove_episodes=False):
        selected_episodes = []

        for index, row in enumerate(self.model):
            if self.model.get_value(row.iter, self.COLUMN_TOGGLE) is True:
                selected_episodes.append(self.episodes[self.model.get_value(
                    row.iter, self.COLUMN_INDEX)])

        if remove_episodes:
            for episode in selected_episodes:
                index = self.episodes.index(episode)
                iter = self.model.get_iter_first()
                while iter is not None:
                    if self.model.get_value(iter, self.COLUMN_INDEX) == index:
                        self.model.remove(iter)
                        break
                    iter = self.model.iter_next(iter)

        return selected_episodes

    def on_btnOK_clicked(self, widget):
        self.gPodderEpisodeSelector.destroy()
        if self.callback is not None:
            self.callback(self.get_selected_episodes())

    def on_btnCancel_clicked(self, widget):
        self.gPodderEpisodeSelector.destroy()
        if self.callback is not None:
            self.callback([])

    def on_notes_back_clicked(self, widget):
        self.new_deck.navigate(Handy.NavigationDirection.BACK)
        return True
