# detachable/group_manager.py
from typing import Dict, Set, Optional, List
import uuid
from enum import Enum

class GroupType(Enum):
    NORMAL = "normal"    # Horizontal gruppiert, gleiche Breite
    STACK = "stack"      # Vertikal gestapelt, automatische Positionierung

class GroupInfo:
    """Informationen über eine Gruppe"""
    def __init__(self, group_id: str, group_type: GroupType):
        self.group_id = group_id
        self.group_type = group_type
        self.members: Set[str] = set()

class GroupManager:
    """
    Verwaltet die Gruppenzugehörigkeit von Widgets.
    ERWEITERT: Unterstützt sowohl normale Gruppen als auch Stack-Gruppen.
    """
    def __init__(self):
        # group_id -> GroupInfo
        self.groups: Dict[str, GroupInfo] = {}
        # widget_key -> group_id  
        self.widget_to_group: Dict[str, str] = {}

    def is_in_group(self, widget_key: str) -> bool:
        """Prüft, ob ein Widget in einer Gruppe ist."""
        return widget_key in self.widget_to_group

    def get_group_id(self, widget_key: str) -> Optional[str]:
        """Gibt die Gruppen-ID für ein Widget zurück."""
        return self.widget_to_group.get(widget_key)

    def get_group_type(self, widget_key: str) -> Optional[GroupType]:
        """Gibt den Gruppentyp für ein Widget zurück."""
        if group_id := self.get_group_id(widget_key):
            return self.groups.get(group_id, GroupInfo("", GroupType.NORMAL)).group_type
        return None

    def get_group_members(self, group_id: str) -> Set[str]:
        """Gibt alle Mitglieder einer Gruppe zurück."""
        if group_id in self.groups:
            return self.groups[group_id].members
        return set()

    def get_all_groups_by_type(self, group_type: GroupType) -> Dict[str, Set[str]]:
        """Gibt alle Gruppen eines bestimmten Typs zurück."""
        return {
            gid: ginfo.members 
            for gid, ginfo in self.groups.items() 
            if ginfo.group_type == group_type
        }

    def add_to_group(self, widget_to_add: str, target_widget: str, group_type: GroupType = GroupType.NORMAL):
        """
        Fügt ein Widget zu einer bestehenden Gruppe hinzu oder erstellt eine neue.
        """
        # Entferne das Widget zunächst aus seiner aktuellen Gruppe
        self.remove_from_group(widget_to_add)
        
        if target_widget in self.widget_to_group:
            # Target ist bereits in einer Gruppe - füge hinzu
            group_id = self.widget_to_group[target_widget]
            existing_group = self.groups[group_id]
            
            # Prüfe ob Gruppentypen kompatibel sind
            if existing_group.group_type != group_type:
                # Konvertiere die gesamte Gruppe zum neuen Typ
                existing_group.group_type = group_type
            
            existing_group.members.add(widget_to_add)
            self.widget_to_group[widget_to_add] = group_id
        else:
            # Erstelle neue Gruppe mit beiden Widgets
            new_group_id = str(uuid.uuid4())
            new_group = GroupInfo(new_group_id, group_type)
            new_group.members = {target_widget, widget_to_add}
            
            self.groups[new_group_id] = new_group
            self.widget_to_group[target_widget] = new_group_id
            self.widget_to_group[widget_to_add] = new_group_id

    def create_stack_group(self, widgets: List[str]) -> Optional[str]:
        """
        Erstellt eine neue Stack-Gruppe mit den angegebenen Widgets.
        Widgets werden in der angegebenen Reihenfolge gestapelt.
        """
        if len(widgets) < 2:
            return None
        
        # Entferne alle Widgets aus ihren aktuellen Gruppen
        for widget in widgets:
            self.remove_from_group(widget)
        
        # Erstelle neue Stack-Gruppe
        new_group_id = str(uuid.uuid4())
        new_group = GroupInfo(new_group_id, GroupType.STACK)
        new_group.members = set(widgets)
        
        self.groups[new_group_id] = new_group
        for widget in widgets:
            self.widget_to_group[widget] = new_group_id
        
        return new_group_id

    def add_to_stack_group(self, widget_to_add: str, target_widget: str):
        """Fügt ein Widget zu einer Stack-Gruppe hinzu."""
        self.add_to_group(widget_to_add, target_widget, GroupType.STACK)

    def remove_from_group(self, widget_key: str):
        """Entfernt ein Widget aus seiner Gruppe."""
        if widget_key not in self.widget_to_group:
            return
        
        group_id = self.widget_to_group.pop(widget_key)
        group_info = self.groups[group_id]
        group_info.members.discard(widget_key)
        
        # Wenn nur noch 1 oder 0 Mitglieder übrig sind, löse die Gruppe auf
        if len(group_info.members) <= 1:
            if group_info.members:
                remaining_member = group_info.members.pop()
                if remaining_member in self.widget_to_group:
                    self.widget_to_group.pop(remaining_member)
            del self.groups[group_id]

    def get_stack_order(self, group_id: str) -> List[str]:
        """
        Gibt die Widgets einer Stack-Gruppe in der korrekten vertikalen Reihenfolge zurück.
        Diese Methode wird vom DetachableManager verwendet, um die Y-Positionen zu bestimmen.
        """
        if group_id not in self.groups or self.groups[group_id].group_type != GroupType.STACK:
            return []
        
        # Die Reihenfolge wird später vom DetachableManager basierend auf aktuellen Y-Positionen bestimmt
        return list(self.groups[group_id].members)

    def convert_group_type(self, group_id: str, new_type: GroupType):
        """Konvertiert eine Gruppe zu einem anderen Typ."""
        if group_id in self.groups:
            self.groups[group_id].group_type = new_type

    def get_group_info(self, group_id: str) -> Optional[GroupInfo]:
        """Gibt vollständige Informationen über eine Gruppe zurück."""
        return self.groups.get(group_id)

    def is_stack_group(self, widget_key: str) -> bool:
        """Prüft, ob ein Widget in einer Stack-Gruppe ist."""
        return self.get_group_type(widget_key) == GroupType.STACK

    def is_normal_group(self, widget_key: str) -> bool:
        """Prüft, ob ein Widget in einer normalen Gruppe ist."""
        return self.get_group_type(widget_key) == GroupType.NORMAL

    def debug_print_groups(self):
        """Debug-Hilfsfunktion zum Ausgeben aller Gruppen."""
        print("=== Gruppen-Status ===")
        for group_id, group_info in self.groups.items():
            print(f"Gruppe {group_id[:8]}... ({group_info.group_type.value}): {group_info.members}")
        print("=== Widget-Zuordnungen ===")
        for widget, group_id in self.widget_to_group.items():
            print(f"Widget {widget} -> Gruppe {group_id[:8]}...")