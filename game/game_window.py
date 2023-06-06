import arcade
from .views.game_view import GameView
from .views.menu_view import MenuView


class GameWindow(arcade.Window):
    def __init__(self, width: int, height: int, title: str):
        self.window_width = width
        self.window_height = height
        self.window_title = title
        self.mem = None
        self.game_view = None
        self.menu_view = None

        super().__init__(self.window_width, self.window_height, self.window_title, resizable=False)

    def setup(self, shared_memory):
        self.mem = shared_memory
        self.game_view = GameView()
        self.menu_view = MenuView()


# class MenuView(arcade.View):
#     def __init__(self):
#         super().__init__()
#         self.mem = self.window.mem
#
#     def on_show_view(self):
#         arcade.set_background_color(arcade.color.WHITE)
#         event = SessionEvent(SessionEvent.SessionCommand.SCOPE)
#         self.mem.queue.put(event)
#
#     def on_draw(self):
#         self.clear()
#         arcade.draw_text("Menu Screen", self.window.width / 2, self.window.height / 2,
#                          arcade.color.BLACK, font_size=50, anchor_x="center")
#         arcade.draw_text("Click to login", self.window.width / 2, self.window.height / 2 - 75,
#                          arcade.color.GRAY, font_size=20, anchor_x="center")
#
#     def on_mouse_press(self, _x, _y, _button, _modifiers):
#         event = SessionEvent(SessionEvent.SessionCommand.LOGIN, character_uuid=self.mem.session.scope.get("characters")[0])
#         self.mem.queue.put(event)
#         time.sleep(0.5)
#         game_view = GameView()
#         self.window.show_view(game_view)


# class GameView(arcade.View):
#     def __init__(self):
#         super().__init__()
#         self.mem = self.window.mem
#         self.player_input = PlayerInput()
#         self.camera = arcade.Camera(self.window.width, self.window.height)
#
#     def setup(self):
#         layer_options = {
#             "Tile Layer 1": {},
#             "Tile Layer 2": {
#                 "use_spatial_hash": True
#             }
#         }
#         map = arcade.tilemap.TileMap(map_file="maps/Minimalistic/0001.tmx", scaling=3, layer_options=layer_options)
#         self.scene = arcade.Scene.from_tilemap(map)
#
#         self.player_sprite = arcade.Sprite("tilesets/Sprite-0002.png", scale=2)
#         self.player_sprite.center_x = self.mem.local_pos[0]
#         self.player_sprite.center_y = self.mem.local_pos[1]
#         self.scene.add_sprite("Tile Layer 2", self.player_sprite)
#
#         self.physics_engine = arcade.PhysicsEngineSimple(self.player_sprite, self.scene.sprite_lists[1])
#
#         arcade.schedule(self.process_input_buffer, PlayerInput.BUFFER_DELAY)
#
#     def on_show_view(self):
#         arcade.set_background_color(arcade.color.BLACK)
#         self.setup()
#
#     def on_draw(self):
#         arcade.start_render()
#         self.camera.use()
#         self.scene.draw(pixelated=True)
#         self.scene.draw_hit_boxes(color=arcade.color.RED, line_thickness=1)
#         self.player_sprite.draw_hit_box(color=arcade.color.RED, line_thickness=1)
#         if self.mem.session.status == GameSession.GameStatus.PLAY:
#             for character_uuid, player in self.mem.gs.player_states.items():
#                 if character_uuid != self.mem.session.character.get("uuid"):
#                     arcade.draw_circle_filled(player.position[0], player.position[1], self.p_radius, arcade.color.BLUE)
#
#     def on_update(self, delta_time: float):
#         self.physics_engine.update()
#         self.mem.local_pos = (self.player_sprite.center_x, self.player_sprite.center_y)
#         self.camera_to_player()
#
#     def movement_lerp(self):
#         DURATION = 0.5
#         local_pos = self.mem.local_pos
#         predicted_server_pos = self.mem.predicted_server_pos
#         local_time = time.time()
#         server_time = self.mem.gamestate_updated_at
#         time_delta = local_time - server_time
#         interp_factor = min(time_delta / DURATION, 1)
#         x_interp = local_pos[0] + interp_factor * (predicted_server_pos[0] - local_pos[0])
#         y_interp = local_pos[1] + interp_factor * (predicted_server_pos[1] - local_pos[1])
#         print(interp_factor, local_pos, predicted_server_pos, (x_interp, y_interp))
#         distance = math.sqrt((x_interp - local_pos[0])**2 + (y_interp - local_pos[1])**2)
#         print(self.mem.local_pixels_traveled, self.mem.server_pixels_traveled, distance)
#         self.mem.local_pixels_traveled += distance
#         self.mem.local_pos = (math.floor(x_interp), math.floor(y_interp))
#
#     def on_key_press(self, symbol: int, modifiers: int):
#         self.player_input.handle_key_press(symbol, modifiers)
#         if symbol == arcade.key.ESCAPE:
#             event = SessionEvent(SessionEvent.SessionCommand.LOGOUT)
#             self.mem.queue.put(event)
#             menu_view = MenuView()
#             self.window.show_view(menu_view)
#
#     def on_key_release(self, symbol: int, modifiers: int):
#         self.player_input.handle_key_release(symbol, modifiers)
#
#     def process_input_buffer(self, delta_time: float):
#         if self.player_input.buffer:
#             with self.player_input.lock:
#                 grouped_events = [event for event in self.player_input.buffer]
#                 self.player_input.add_keys({event[0] for event in grouped_events if event[1] is True})
#                 self.player_input.remove_keys({event[0] for event in grouped_events if event[1] is False})
#                 self.player_input.buffer.clear()
#                 self.update_player_movement()
#
#     def update_player_movement(self):
#         velocity = calculate_velocity(self.player_input.to_bitfield())
#         self.player_sprite.change_x, self.player_sprite.change_y = velocity
#
#     def camera_to_player(self):
#         if self.mem.gs.player_states:
#             screen_center_x = self.player_sprite.center_x - self.window.width / 2
#             screen_center_y = self.player_sprite.center_y - self.window.height / 2
#             if screen_center_x < 0: screen_center_x = 0
#             if screen_center_y < 0: screen_center_y = 0
#             player_centered = screen_center_x, screen_center_y
#             self.camera.move_to(player_centered, 0.1)


# class GameView(arcade.View):
#     def __init__(self):
#         super().__init__()
#         self.mem = self.window.mem
#         self.player_input = PlayerInput()
#         self.camera = arcade.Camera(self.window.width, self.window.height)
#
#         self.p_radius = 30
#
#     def setup(self):
#         layer_options = {
#             "Tile Layer 1": {},
#             "Tile Layer 2": {
#                 "use_spatial_hash": True
#             }
#         }
#         map = arcade.tilemap.TileMap(map_file="maps/test.json", scaling=3, layer_options=layer_options)
#         self.scene = arcade.Scene.from_tilemap(map)
#         self.scene.sprite_lists[1].extend(self.scene.sprite_lists[2])
#         del self.scene.sprite_lists[2]
#
#         self.player_sprite = arcade.Sprite("tilesets/Sprite-0002.png", scale=2)
#         self.player_sprite.center_x = self.mem.local_pos[0]
#         self.player_sprite.center_y = self.mem.local_pos[1]
#         self.scene.add_sprite("Tile Layer 2", self.player_sprite)
#         self.player_sprite.hit_box = ((1, -17), (0, -17), (-1, -16), (-15, -23), (-15, -24), (-15, -25), (-1, -31), (0, -31), (1, -31), (15, -25), (15, -24), (15, -23))
#
#         self.physics_engine = PymunkPhysicsEngine(damping=1)
#         self.physics_engine.add_sprite(self.player_sprite,
#                                        friction=0.6,
#                                        moment_of_inertia=PymunkPhysicsEngine.MOMENT_INF,
#                                        damping=0.01,
#                                        collision_type="player",
#                                        max_velocity=400)
#
#         # self.physics_engine.add_sprite_list(self.scene["Tile Layer 2"],
#         #                                     friction=0.1,
#         #                                     collision_type="wall",
#         #                                     body_type=PymunkPhysicsEngine.STATIC)
#
#         arcade.schedule(self.process_input_buffer, PlayerInput.BUFFER_DELAY)
#
#     def on_show_view(self):
#         arcade.set_background_color(arcade.color.BLACK)
#         self.setup()
#
#     def on_draw(self):
#         arcade.start_render()
#         self.camera.use()
#         self.scene.draw(pixelated=True)
#         # self.scene.draw_hit_boxes(color=arcade.color.RED, line_thickness=1)
#         self.player_sprite.draw_hit_box(color=arcade.color.RED, line_thickness=1)
#         if self.mem.session.status == GameSession.GameStatus.PLAY:
#             for character_uuid, player in self.mem.gs.player_states.items():
#                 if character_uuid != self.mem.session.character.get("uuid"):
#                     arcade.draw_circle_filled(player.position[0], player.position[1], self.p_radius, arcade.color.BLUE)
#
#     def on_update(self, delta_time: float):
#         if self.mem.local_velocity[0] != 0 or self.mem.local_velocity[1] != 0:
#             player_vel = Vec2d(self.mem.local_velocity[0], self.mem.local_velocity[1])
#             player_vel *= 1000
#             self.physics_engine.apply_force(self.player_sprite, player_vel)
#
#         self.physics_engine.step()
#
#         self.mem.local_pos = (self.player_sprite.center_x, self.player_sprite.center_y)
#
#         # self.scene["Tile Layer 2"].sort(key=lambda x: (x.z_index, x.position[1] - x.height / 2), reverse=True)
#         self.camera_to_player()
#
#     def movement_lerp(self):
#         DURATION = 0.5
#         local_pos = self.mem.local_pos
#         predicted_server_pos = self.mem.predicted_server_pos
#         local_time = time.time()
#         server_time = self.mem.gamestate_updated_at
#         time_delta = local_time - server_time
#         interp_factor = min(time_delta / DURATION, 1)
#         x_interp = local_pos[0] + interp_factor * (predicted_server_pos[0] - local_pos[0])
#         y_interp = local_pos[1] + interp_factor * (predicted_server_pos[1] - local_pos[1])
#         print(interp_factor, local_pos, predicted_server_pos, (x_interp, y_interp))
#         distance = math.sqrt((x_interp - local_pos[0])**2 + (y_interp - local_pos[1])**2)
#         print(self.mem.local_pixels_traveled, self.mem.server_pixels_traveled, distance)
#         self.mem.local_pixels_traveled += distance
#         self.mem.local_pos = (math.floor(x_interp), math.floor(y_interp))
#
#     def on_key_press(self, symbol: int, modifiers: int):
#         self.player_input.handle_key_press(symbol, modifiers)
#         if symbol == arcade.key.ESCAPE:
#             event = SessionEvent(SessionEvent.SessionCommand.LOGOUT)
#             self.mem.queue.put(event)
#             menu_view = MenuView()
#             self.window.show_view(menu_view)
#
#     def on_key_release(self, symbol: int, modifiers: int):
#         self.player_input.handle_key_release(symbol, modifiers)
#
#     def process_input_buffer(self, delta_time: float):
#         if self.player_input.buffer:
#             with self.player_input.lock:
#                 grouped_events = [event for event in self.player_input.buffer]
#                 self.player_input.add_keys({event[0] for event in grouped_events if event[1] == True})
#                 self.player_input.remove_keys({event[0] for event in grouped_events if event[1] == False})
#                 self.player_input.buffer.clear()
#                 self.mem.local_velocity = calculate_velocity(self.player_input.to_bitfield())
#
#     def camera_to_player(self):
#         if self.mem.gs.player_states:
#             screen_center_x = self.player_sprite.center_x - self.window.width / 2
#             screen_center_y = self.player_sprite.center_y - self.window.height / 2
#             if screen_center_x < 0: screen_center_x = 0
#             if screen_center_y < 0: screen_center_y = 0
#             player_centered = screen_center_x, screen_center_y
#             self.camera.move_to(player_centered, 0.1)
