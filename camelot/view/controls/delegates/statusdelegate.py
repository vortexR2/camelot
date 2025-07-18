import logging

from camelot.core.item_model import IsStatusRole, PreviewRole
from camelot.core.qt import Qt

from dataclasses import dataclass

from .comboboxdelegate import EnumDelegate

logger = logging.getLogger(__name__)


@dataclass
class StatusDelegate(EnumDelegate):

    @classmethod
    def get_editor_class(cls):
        return None

    @classmethod
    def get_standard_item(cls, locale, model_context):
        item = super().get_standard_item(locale, model_context)
        cls.set_item_editability(model_context, item, False)
        if model_context.value is not None:
            if (types := model_context.field_attributes.get('types')) is not None and model_context.value in types:
                if (color := types[model_context.value].color) is not None:
                    item.roles[Qt.ItemDataRole.ForegroundRole] = color
        item.roles[Qt.ItemDataRole.TextAlignmentRole] = Qt.AlignmentFlag.AlignHCenter
        item.roles[IsStatusRole] = True
        return item

    def setEditorData(self, editor, index):
        if index.model() is None:
            return
        value = index.model().data(index, PreviewRole)
        editor.set_value(value)
