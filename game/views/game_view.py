import arcade
from common.lib import PlayerInput, GameSession, SessionEvent, calculate_velocity


class GameView(arcade.View):
    def __init__(self):
        super().__init__()
        self.mem = self.window.mem
        self.player_input = PlayerInput()
        self.camera = arcade.Camera(self.window.width, self.window.height)

    def setup(self):
        layer_options = {
            "Tile Layer 1": {},
            "Tile Layer 2": {
                "use_spatial_hash": True
            }
        }
        map = arcade.tilemap.TileMap(map_file="maps/Minimalistic/0001.tmx", scaling=3, layer_options=layer_options)
        self.scene = arcade.Scene.from_tilemap(map)

        self.player_sprite = arcade.Sprite("tilesets/Sprite-0002.png", scale=2)
        self.player_sprite.center_x = self.mem.local_pos[0]
        self.player_sprite.center_y = self.mem.local_pos[1]
        self.scene.add_sprite("Tile Layer 2", self.player_sprite)

        self.physics_engine = arcade.PhysicsEngineSimple(self.player_sprite, self.scene.sprite_lists[1])

        arcade.schedule(self.process_input_buffer, PlayerInput.BUFFER_DELAY)

    def on_show_view(self):
        arcade.set_background_color(arcade.color.BLACK)
        self.setup()

    def on_draw(self):
        arcade.start_render()
        self.camera.use()
        self.scene.draw(pixelated=True)
        self.scene.draw_hit_boxes(color=arcade.color.RED, line_thickness=1)
        self.player_sprite.draw_hit_box(color=arcade.color.RED, line_thickness=1)
        if self.mem.session.status == GameSession.GameStatus.PLAY:
            for character_uuid, player in self.mem.gs.player_states.items():
                if character_uuid != self.mem.session.character.get("uuid"):
                    arcade.draw_circle_filled(player.position[0], player.position[1], self.p_radius, arcade.color.BLUE)

    def on_update(self, delta_time: float):
        self.physics_engine.update()
        self.mem.local_pos = (self.player_sprite.center_x, self.player_sprite.center_y)
        self.camera_to_player()

    def on_key_press(self, symbol: int, modifiers: int):
        self.player_input.handle_key_press(symbol, modifiers)
        if symbol == arcade.key.ESCAPE:
            event = SessionEvent(SessionEvent.SessionCommand.LOGOUT)
            self.mem.queue.put(event)
            self.window.show_view(self.window.menu_view)

    def on_key_release(self, symbol: int, modifiers: int):
        self.player_input.handle_key_release(symbol, modifiers)

    def process_input_buffer(self, delta_time: float):
        if self.player_input.buffer:
            with self.player_input.lock:
                grouped_events = [event for event in self.player_input.buffer]
                self.player_input.add_keys({event[0] for event in grouped_events if event[1] is True})
                self.player_input.remove_keys({event[0] for event in grouped_events if event[1] is False})
                self.player_input.buffer.clear()
                self.update_player_movement()

    def update_player_movement(self):
        velocity = calculate_velocity(self.player_input.to_bitfield())
        self.player_sprite.change_x, self.player_sprite.change_y = velocity

    def camera_to_player(self):
        if self.mem.gs.player_states:
            screen_center_x = self.player_sprite.center_x - self.window.width / 2
            screen_center_y = self.player_sprite.center_y - self.window.height / 2
            if screen_center_x < 0: screen_center_x = 0
            if screen_center_y < 0: screen_center_y = 0
            player_centered = screen_center_x, screen_center_y
            self.camera.move_to(player_centered, 0.1)