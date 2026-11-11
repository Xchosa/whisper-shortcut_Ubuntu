"""Small GTK history selector; storage and recording actions belong to Demo."""
from datetime import datetime
from gi.repository import Gtk


class HistoryPanel:
    def __init__(self, translate, opened, deleted, paged):
        self.translate = translate
        self.entries = []
        self.widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.widget.append(Gtk.Label(label=translate("Local history"), xalign=0))
        self.selector = Gtk.DropDown.new_from_strings([translate("No saved entries")])
        self.widget.append(self.selector)
        row = Gtk.Box(spacing=6)
        self.widget.append(row)
        for label, action in [
            ("Open selected", lambda: self.selected(opened)),
            ("Delete selected", lambda: self.selected(deleted)),
            ("Newer", lambda: paged(-1)),
            ("Older", lambda: paged(1)),
        ]:
            button = Gtk.Button(label=translate(label))
            button.connect("clicked", lambda _, callback=action: callback())
            row.append(button)
            if label == "Newer":
                self.newer = button
            elif label == "Older":
                self.older = button

    def selected(self, callback):
        index = self.selector.get_selected()
        if index < len(self.entries):
            callback(self.entries[index].id)

    def update(self, entries, offset, current_id):
        self.entries = entries
        labels = []
        for entry in entries:
            try:
                date = datetime.fromisoformat(entry.created_at).astimezone().strftime("%Y-%m-%d %H:%M")
            except ValueError:
                date = self.translate("Unknown date")
            preview = " ".join(entry.preview.split())
            labels.append(f"{date} · {self.translate(entry.status)} · {preview}")
        self.selector.set_model(Gtk.StringList.new(labels or [self.translate("No saved entries")]))
        for index, entry in enumerate(entries):
            if entry.id == current_id:
                self.selector.set_selected(index)
                break
        self.newer.set_sensitive(offset > 0)
        self.older.set_sensitive(len(entries) == 100)
