"""Set di icone SVG inline (stroke, 24x24, ereditano currentColor).

Sostituiscono le emoji: resa identica su ogni sistema operativo e aspetto
coerente con il resto dell'interfaccia.
"""
from __future__ import annotations

_W = ('<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
      'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')

_PATHS = {
    "activity":  '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    "chart":     '<path d="M3 3v18h18"/><path d="m7 15 4-5 3 3 5-7"/>',
    "settings":  '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 7 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H1a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 2.6 7a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 7 2.6h.1A1.6 1.6 0 0 0 8.7 1V1a2 2 0 1 1 4 0v.1A1.6 1.6 0 0 0 15 2.6a1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
    "store":     '<path d="M3 9.5 4.5 4h15L21 9.5"/><path d="M3 9.5h18v10a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19.5z"/><path d="M8 21v-6h8v6"/>',
    "package":   '<path d="m12 2 9 5v10l-9 5-9-5V7z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 12v10"/>',
    "search":    '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "download":  '<path d="M12 3v12"/><path d="m7 11 5 5 5-5"/><path d="M4 20h16"/>',
    "save":      '<path d="M4 4h12l4 4v12H4z"/><path d="M8 4v6h8V4"/><path d="M8 20v-6h8v6"/>',
    "plus":      '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "alert":     '<path d="M12 3 2 20h20z"/><path d="M12 9v5"/><path d="M12 17.5h.01"/>',
    "external":  '<path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M18 14v5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 19V8a1.5 1.5 0 0 1 1.5-1.5H10"/>',
    "cart":      '<circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/><path d="M2 3h3l2.5 12h11L21 7H6"/>',
    "list":      '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3.5 6h.01"/><path d="M3.5 12h.01"/><path d="M3.5 18h.01"/>',
    "filter":    '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>',
    "refresh":   '<path d="M20 11A8 8 0 0 0 6.3 6.3L3 9.5"/><path d="M4 13a8 8 0 0 0 13.7 4.7L21 14.5"/><path d="M3 4.5v5h5"/><path d="M21 19.5v-5h-5"/>',
    "tag":       '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><path d="M7.5 7.5h.01"/>',
    "image":     '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="m21 16-5-5L6 20"/>',
}


def icon(name: str, cls: str = "ic") -> str:
    body = _PATHS.get(name)
    if not body:
        return ""
    return _W.format(cls=cls, body=body)
