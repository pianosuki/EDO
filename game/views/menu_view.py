import arcade, time
from common.lib import SessionEvent


class MenuView(arcade.View):
    def __init__(self):
        super().__init__()
        self.mem = self.window.mem

    def on_show_view(self):
        arcade.set_background_color(arcade.color.WHITE)
        event = SessionEvent(SessionEvent.SessionCommand.SCOPE)
        self.mem.queue.put(event)

    def on_draw(self):
        self.clear()
        arcade.draw_text("Menu Screen", self.window.width / 2, self.window.height / 2,
                         arcade.color.BLACK, font_size=50, anchor_x="center")
        arcade.draw_text("Click to login", self.window.width / 2, self.window.height / 2 - 75,
                         arcade.color.GRAY, font_size=20, anchor_x="center")

    def on_mouse_press(self, _x, _y, _button, _modifiers):
        event = SessionEvent(SessionEvent.SessionCommand.LOGIN, character_uuid=self.mem.session.scope.get("characters")[0])
        self.mem.queue.put(event)
        time.sleep(0.5)
        self.window.show_view(self.window.game_view)
