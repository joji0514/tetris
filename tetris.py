import random
import time
import tkinter as tk


CELL_SIZE = 30
BOARD_WIDTH = 10
BOARD_HEIGHT = 20
SIDE_PANEL_WIDTH = 180
PADDING = 20
TICK_MS = 500
FAST_TICK_MS = 50
MIN_TICK_MS = 120
LEVEL_UP_EVERY_SECONDS = 30
TICK_SPEED_STEP = 45
CLEAR_EFFECT_DURATION = 0.45

SHAPES = {
    "I": [
        [1, 1, 1, 1],
    ],
    "O": [
        [1, 1],
        [1, 1],
    ],
    "T": [
        [0, 1, 0],
        [1, 1, 1],
    ],
    "S": [
        [0, 1, 1],
        [1, 1, 0],
    ],
    "Z": [
        [1, 1, 0],
        [0, 1, 1],
    ],
    "J": [
        [1, 0, 0],
        [1, 1, 1],
    ],
    "L": [
        [0, 0, 1],
        [1, 1, 1],
    ],
}

COLORS = {
    "I": "#39c5bb",
    "O": "#f3d250",
    "T": "#d66fd3",
    "S": "#66bb6a",
    "Z": "#ef5350",
    "J": "#5c6bc0",
    "L": "#ffa726",
}


def rotate_clockwise(matrix):
    return [list(row) for row in zip(*matrix[::-1])]


class TetrisGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Tetris")
        self.root.resizable(False, False)

        canvas_width = BOARD_WIDTH * CELL_SIZE + SIDE_PANEL_WIDTH + PADDING * 3
        canvas_height = BOARD_HEIGHT * CELL_SIZE + PADDING * 2
        self.canvas = tk.Canvas(
            root,
            width=canvas_width,
            height=canvas_height,
            bg="#111827",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.board_left = PADDING
        self.board_top = PADDING
        self.panel_left = self.board_left + BOARD_WIDTH * CELL_SIZE + PADDING

        self.after_id = None
        self.reset_game()
        self.bind_keys()
        self.draw()
        self.schedule_tick()

    def reset_game(self):
        self.board = [[None for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.soft_drop = False
        self.started_at = time.monotonic()
        self.clear_effect_until = 0.0
        self.clear_effect_text = ""
        self.bag = []
        self.current_piece = self.create_piece()
        self.next_piece = self.create_piece()

    def bind_keys(self):
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease-Down>", self.on_key_release)

    def on_key_press(self, event):
        if self.game_over and event.keysym.lower() == "r":
            self.restart()
            return

        if self.game_over:
            return

        if event.keysym == "Left":
            self.move_piece(-1, 0)
        elif event.keysym == "Right":
            self.move_piece(1, 0)
        elif event.keysym == "Down":
            self.soft_drop = True
            self.reschedule_tick()
        elif event.keysym in ("Up", "x"):
            self.rotate_piece()
        elif event.keysym == "z":
            self.rotate_piece(counterclockwise=True)
        elif event.keysym == "space":
            self.hard_drop()

        self.draw()

    def on_key_release(self, event):
        if event.keysym == "Down":
            self.soft_drop = False
            self.reschedule_tick()

    def restart(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
        self.reset_game()
        self.draw()
        self.schedule_tick()

    def refill_bag(self):
        self.bag = list(SHAPES.keys())
        random.shuffle(self.bag)

    def create_piece(self):
        if not self.bag:
            self.refill_bag()
        kind = self.bag.pop()
        shape = [row[:] for row in SHAPES[kind]]
        x = BOARD_WIDTH // 2 - len(shape[0]) // 2
        y = -self.top_padding(shape)
        return {"kind": kind, "shape": shape, "x": x, "y": y}

    def top_padding(self, shape):
        padding = 0
        for row in shape:
            if any(row):
                break
            padding += 1
        return padding

    def move_piece(self, dx, dy):
        new_x = self.current_piece["x"] + dx
        new_y = self.current_piece["y"] + dy
        if self.is_valid_position(self.current_piece["shape"], new_x, new_y):
            self.current_piece["x"] = new_x
            self.current_piece["y"] = new_y
            return True
        return False

    def rotate_piece(self, counterclockwise=False):
        shape = self.current_piece["shape"]
        rotated = shape
        for _ in range(3 if counterclockwise else 1):
            rotated = rotate_clockwise(rotated)

        for offset in (0, -1, 1, -2, 2):
            new_x = self.current_piece["x"] + offset
            if self.is_valid_position(rotated, new_x, self.current_piece["y"]):
                self.current_piece["shape"] = rotated
                self.current_piece["x"] = new_x
                return

    def hard_drop(self):
        while self.move_piece(0, 1):
            self.score += 2
        self.lock_piece()
        self.draw()

    def is_valid_position(self, shape, offset_x, offset_y):
        for row_index, row in enumerate(shape):
            for col_index, cell in enumerate(row):
                if not cell:
                    continue

                x = offset_x + col_index
                y = offset_y + row_index

                if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                    return False
                if y >= 0 and self.board[y][x] is not None:
                    return False
        return True

    def lock_piece(self):
        piece = self.current_piece
        for row_index, row in enumerate(piece["shape"]):
            for col_index, cell in enumerate(row):
                if not cell:
                    continue
                x = piece["x"] + col_index
                y = piece["y"] + row_index
                if y < 0:
                    self.game_over = True
                    return
                self.board[y][x] = piece["kind"]

        cleared = self.clear_lines()
        if cleared:
            self.lines += cleared
            self.score += {1: 100, 2: 300, 3: 500, 4: 800}[cleared]
            self.trigger_clear_effect(cleared)

        self.current_piece = self.next_piece
        self.next_piece = self.create_piece()
        if not self.is_valid_position(
            self.current_piece["shape"],
            self.current_piece["x"],
            self.current_piece["y"],
        ):
            self.game_over = True

    def clear_lines(self):
        remaining_rows = [row for row in self.board if any(cell is None for cell in row)]
        cleared = BOARD_HEIGHT - len(remaining_rows)
        while len(remaining_rows) < BOARD_HEIGHT:
            remaining_rows.insert(0, [None for _ in range(BOARD_WIDTH)])
        self.board = remaining_rows
        return cleared

    def trigger_clear_effect(self, cleared):
        suffix = "!" * min(4, cleared)
        self.clear_effect_text = f"ゲリィ！！{suffix}"
        self.clear_effect_until = time.monotonic() + CLEAR_EFFECT_DURATION

    def update_level(self):
        elapsed = time.monotonic() - self.started_at
        self.level = 1 + int(elapsed // LEVEL_UP_EVERY_SECONDS)

    def tick(self):
        if not self.game_over:
            self.update_level()
            moved = self.move_piece(0, 1)
            if not moved:
                self.lock_piece()
            self.draw()

        self.schedule_tick()

    def schedule_tick(self):
        base_interval = max(MIN_TICK_MS, TICK_MS - (self.level - 1) * TICK_SPEED_STEP)
        interval = FAST_TICK_MS if self.soft_drop and not self.game_over else base_interval
        self.after_id = self.root.after(interval, self.tick)

    def reschedule_tick(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
        self.schedule_tick()

    def draw_cell(self, x, y, color, outline="#0f172a"):
        px = self.board_left + x * CELL_SIZE
        py = self.board_top + y * CELL_SIZE
        self.canvas.create_rectangle(
            px,
            py,
            px + CELL_SIZE,
            py + CELL_SIZE,
            fill=color,
            outline=outline,
            width=2,
        )

    def draw_board(self):
        width = BOARD_WIDTH * CELL_SIZE
        height = BOARD_HEIGHT * CELL_SIZE
        self.canvas.create_rectangle(
            self.board_left - 2,
            self.board_top - 2,
            self.board_left + width + 2,
            self.board_top + height + 2,
            fill="#1f2937",
            outline="#e5e7eb",
            width=2,
        )

        for y in range(BOARD_HEIGHT):
            for x in range(BOARD_WIDTH):
                self.draw_cell(x, y, "#111827", outline="#1f2937")
                kind = self.board[y][x]
                if kind is not None:
                    self.draw_cell(x, y, COLORS[kind])

    def draw_piece(self, piece, ghost=False, preview=False):
        shape = piece["shape"]
        kind = piece["kind"]
        color = COLORS[kind]
        if ghost:
            color = ""

        preview_origin_x = self.panel_left + 32
        preview_origin_y = self.board_top + 190
        preview_width = 4 * CELL_SIZE
        preview_height = 4 * CELL_SIZE
        shape_width = len(shape[0]) * CELL_SIZE
        shape_height = len(shape) * CELL_SIZE
        preview_offset_x = (preview_width - shape_width) / 2
        preview_offset_y = (preview_height - shape_height) / 2

        for row_index, row in enumerate(shape):
            for col_index, cell in enumerate(row):
                if not cell:
                    continue

                if preview:
                    x = preview_origin_x + preview_offset_x + col_index * CELL_SIZE
                    y = preview_origin_y + preview_offset_y + row_index * CELL_SIZE
                    self.canvas.create_rectangle(
                        x,
                        y,
                        x + CELL_SIZE,
                        y + CELL_SIZE,
                        fill=COLORS[kind],
                        outline="#0f172a",
                        width=2,
                    )
                else:
                    board_x = piece["x"] + col_index
                    board_y = piece["y"] + row_index
                    if board_y < 0:
                        continue
                    if ghost:
                        px = self.board_left + board_x * CELL_SIZE
                        py = self.board_top + board_y * CELL_SIZE
                        self.canvas.create_rectangle(
                            px + 5,
                            py + 5,
                            px + CELL_SIZE - 5,
                            py + CELL_SIZE - 5,
                            outline=COLORS[kind],
                            width=2,
                        )
                    else:
                        self.draw_cell(board_x, board_y, color)

    def ghost_piece(self):
        ghost = {
            "kind": self.current_piece["kind"],
            "shape": [row[:] for row in self.current_piece["shape"]],
            "x": self.current_piece["x"],
            "y": self.current_piece["y"],
        }
        while self.is_valid_position(ghost["shape"], ghost["x"], ghost["y"] + 1):
            ghost["y"] += 1
        return ghost

    def draw_side_panel(self):
        panel_right = self.panel_left + SIDE_PANEL_WIDTH
        self.canvas.create_rectangle(
            self.panel_left,
            self.board_top,
            panel_right,
            self.board_top + BOARD_HEIGHT * CELL_SIZE,
            fill="#0f172a",
            outline="",
        )

        self.canvas.create_text(
            self.panel_left + 20,
            self.board_top + 30,
            text="TETRIS",
            anchor="w",
            fill="#f8fafc",
            font=("Helvetica", 24, "bold"),
        )
        self.canvas.create_text(
            self.panel_left + 20,
            self.board_top + 80,
            text=f"Score: {self.score}",
            anchor="w",
            fill="#cbd5e1",
            font=("Helvetica", 16, "bold"),
        )
        self.canvas.create_text(
            self.panel_left + 20,
            self.board_top + 110,
            text=f"Lines: {self.lines}",
            anchor="w",
            fill="#cbd5e1",
            font=("Helvetica", 16, "bold"),
        )
        self.canvas.create_text(
            self.panel_left + 20,
            self.board_top + 140,
            text=f"Level: {self.level}",
            anchor="w",
            fill="#cbd5e1",
            font=("Helvetica", 16, "bold"),
        )
        self.canvas.create_text(
            self.panel_left + 20,
            self.board_top + 180,
            text="Next",
            anchor="w",
            fill="#f8fafc",
            font=("Helvetica", 16, "bold"),
        )
        self.canvas.create_rectangle(
            self.panel_left + 28,
            self.board_top + 186,
            self.panel_left + 28 + 4 * CELL_SIZE + 8,
            self.board_top + 186 + 4 * CELL_SIZE + 8,
            outline="#334155",
            width=2,
        )

        self.draw_piece(
            {"kind": self.next_piece["kind"], "shape": self.next_piece["shape"], "x": 0, "y": 0},
            preview=True,
        )

        controls = [
            "Left/Right: move",
            "Up/X: rotate",
            "Z: reverse rotate",
            "Down: soft drop",
            "Space: hard drop",
            "R: restart",
        ]

        for index, text in enumerate(controls):
            self.canvas.create_text(
                self.panel_left + 20,
                self.board_top + 350 + index * 28,
                text=text,
                anchor="w",
                fill="#94a3b8",
                font=("Helvetica", 12),
            )

    def draw_clear_effect(self):
        if time.monotonic() > self.clear_effect_until:
            return

        pulse = int(time.monotonic() * 12) % 2
        accent = "#fde047" if pulse else "#fb7185"
        self.canvas.create_rectangle(
            self.board_left + 12,
            self.board_top + 240,
            self.board_left + BOARD_WIDTH * CELL_SIZE - 12,
            self.board_top + 330,
            fill="#111827",
            outline=accent,
            width=4,
        )
        self.canvas.create_text(
            self.board_left + BOARD_WIDTH * CELL_SIZE / 2,
            self.board_top + 285,
            text=self.clear_effect_text,
            fill=accent,
            font=("Helvetica", 28, "bold"),
        )

    def draw_game_over(self):
        x1 = self.board_left + 20
        y1 = self.board_top + 220
        x2 = self.board_left + BOARD_WIDTH * CELL_SIZE - 20
        y2 = self.board_top + 380
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#000000", outline="#f8fafc", width=2)
        self.canvas.create_text(
            (x1 + x2) / 2,
            y1 + 45,
            text="Game Over",
            fill="#f8fafc",
            font=("Helvetica", 24, "bold"),
        )
        self.canvas.create_text(
            (x1 + x2) / 2,
            y1 + 90,
            text=f"Score: {self.score}",
            fill="#cbd5e1",
            font=("Helvetica", 16),
        )
        self.canvas.create_text(
            (x1 + x2) / 2,
            y1 + 125,
            text="Press R to restart",
            fill="#cbd5e1",
            font=("Helvetica", 14),
        )

    def draw(self):
        self.canvas.delete("all")
        self.draw_board()
        self.draw_side_panel()
        self.draw_piece(self.ghost_piece(), ghost=True)
        self.draw_piece(self.current_piece)
        self.draw_clear_effect()

        if self.game_over:
            self.draw_game_over()


def main():
    root = tk.Tk()
    TetrisGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
