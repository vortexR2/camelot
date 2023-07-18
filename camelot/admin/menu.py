#  ============================================================================
#
#  Copyright (C) 2007-2016 Conceptive Engineering bvba.
#  www.conceptive.be / info@conceptive.be
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of Conceptive Engineering nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#  
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  ============================================================================

from dataclasses import dataclass, field
import typing

from .admin_route import Route
from .icon import Icon
from ..core.serializable import DataclassSerializable
from ..core.utils import ugettext_lazy

@dataclass
class MenuItem(DataclassSerializable):
    """A MenuItem is a part of a menu. A MenuItem can either have a verbose_name
    and an icon and be a menu in itself, or it can have an action.  If the
    MenuItem has neither of those, it acts as a separator.

    Using subclasses is avoided here to to keep serializability of nested
    menu items straightforward.
    """

    verbose_name: typing.Union[str, ugettext_lazy, None] = None
    icon: typing.Union[Icon, None] = None
    action_route: typing.Union[Route, None] = None
    role: typing.Optional[str] = None
    items: typing.List['MenuItem'] = field(default_factory=list)
    open: bool = False

    def __post_init__(self, ):
        assert (self.action_route is None) or ((self.verbose_name is None) and (self.icon is None))
