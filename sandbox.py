import math, time, threading
import numpy as np
import glfw
from OpenGL.GL import *
import tkinter as tk

# --- OpenGL setup ---
VERTEX_SHADER = """
#version 330 core
layout (location = 0) in vec2 aPos;
uniform mat4 uTransform;
void main() {
    gl_Position = uTransform * vec4(aPos, 0.0, 1.0);
}
"""
FRAGMENT_SHADER = """
#version 330 core
out vec4 FragColor;
uniform vec3 uColor;
void main() {
    FragColor = vec4(uColor, 1.0);
}
"""

def compile_shader(src, shader_type):
    s = glCreateShader(shader_type)
    glShaderSource(s, src)
    glCompileShader(s)
    if not glGetShaderiv(s, GL_COMPILE_STATUS):
        raise RuntimeError(glGetShaderInfoLog(s).decode())
    return s

def make_program(vs_src, fs_src):
    vs = compile_shader(vs_src, GL_VERTEX_SHADER)
    fs = compile_shader(fs_src, GL_FRAGMENT_SHADER)
    p = glCreateProgram()
    glAttachShader(p, vs)
    glAttachShader(p, fs)
    glLinkProgram(p)
    glDeleteShader(vs)
    glDeleteShader(fs)
    return p

def make_grid(n=30):
    lines = []
    for i in range(-n, n + 1):
        lines += [i, -n, i, n]
        lines += [-n, i, n, i]
    return np.array(lines, dtype=np.float32)

def make_vector(x, y):
    # base line
    vertices = [0, 0, x, y]

    # arrowhead size (in model space units)
    head_len = 0.3
    head_ang = math.radians(20)

    # direction
    angle = math.atan2(y, x)
    left = angle + math.pi - head_ang
    right = angle + math.pi + head_ang

    x2, y2 = x, y
    # left wing
    vertices += [x2, y2, x2 + head_len * math.cos(left), y2 + head_len * math.sin(left)]
    # right wing
    vertices += [x2, y2, x2 + head_len * math.cos(right), y2 + head_len * math.sin(right)]

    return np.array(vertices, dtype=np.float32)


# --- Render thread ---
def render_loop(shared):
    time.sleep(0.5)  # Give Tkinter time to appear
    if not glfw.init():
        raise Exception("GLFW init failed")
    win = glfw.create_window(800, 800, "Matrix Sandbox (Tk Controls)", None, None)
    glfw.make_context_current(win)

    prog = make_program(VERTEX_SHADER, FRAGMENT_SHADER)
    glUseProgram(prog)

    grid = make_grid(10)
    vec = make_vector(3, 1)

    vbo_grid = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo_grid)
    glBufferData(GL_ARRAY_BUFFER, grid.nbytes, grid, GL_STATIC_DRAW)

    vbo_vec = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo_vec)
    glBufferData(GL_ARRAY_BUFFER, vec.nbytes, vec, GL_STATIC_DRAW)

    color_loc = glGetUniformLocation(prog, "uColor")
    trans_loc = glGetUniformLocation(prog, "uTransform")
    glClearColor(0.1, 0.1, 0.1, 1.0)

    while not glfw.window_should_close(win):
        glfw.poll_events()
        if shared["paused"].get():
            time.sleep(0.01)
            continue

        # time relative to reset
        t = time.time() - shared["t0"]
        env = {"math": math, "t": t}

        def safe_eval(expr):
            try:
                return float(eval(expr, {"__builtins__": {}, "math": math, "t": env["t"]}))
            except Exception:
                return 0.0

        a = safe_eval(shared["a_expr"].get()) * shared["a_scale"].get()
        b = safe_eval(shared["b_expr"].get()) * shared["b_scale"].get()
        c = safe_eval(shared["c_expr"].get()) * shared["c_scale"].get()
        d = safe_eval(shared["d_expr"].get()) * shared["d_scale"].get()

        M = np.array([[a, b, 0, 0],
                      [c, d, 0, 0],
                      [0, 0, 1, 0],
                      [0, 0, 0, 1]], dtype=np.float32)

        glClear(GL_COLOR_BUFFER_BIT)
        glUniformMatrix4fv(trans_loc, 1, GL_FALSE, M)

        # --- grid ---
        if shared["show_grid"].get():
            glUniform3f(color_loc, 0.5, 0.5, 0.5)
            glBindBuffer(GL_ARRAY_BUFFER, vbo_grid)
            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(0)
            glDrawArrays(GL_LINES, 0, len(grid)//2)

        # --- vector with arrowhead ---
        if shared["show_arrow"].get():
            glUniform3f(color_loc, 1.0, 0.2, 0.2)
            glBindBuffer(GL_ARRAY_BUFFER, vbo_vec)
            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
            glEnableVertexAttribArray(0)
            glDrawArrays(GL_LINES, 0, 6)

        glfw.swap_buffers(win)

    glfw.terminate()


# --- Tkinter controls (main thread) ---
def make_controls():
    root = tk.Tk()
    root.title("Matrix Controls")
        
    shared = {
        "a_expr": tk.StringVar(value="math.cos(t)"),
        "b_expr": tk.StringVar(value="math.sin(t)"),
        "c_expr": tk.StringVar(value="-math.sin(t)"),
        "d_expr": tk.StringVar(value="math.cos(t)"),
        "a_scale": tk.DoubleVar(value=1.0),
        "b_scale": tk.DoubleVar(value=1.0),
        "c_scale": tk.DoubleVar(value=1.0),
        "d_scale": tk.DoubleVar(value=1.0),
        "paused": tk.BooleanVar(value=False),
        "show_grid": tk.BooleanVar(value=True),
        "show_arrow": tk.BooleanVar(value=True),
        "t0": time.time(),  # reference time
    }

    def reset_t():
        shared["t0"] = time.time()

    def add_row(row, label, expr_var, scale_var):
        tk.Label(root, text=label).grid(row=row, column=0)
        tk.Entry(root, textvariable=expr_var, width=25).grid(row=row, column=1)
        tk.Scale(root, variable=scale_var, from_=-2, to=2,
                 orient="horizontal", resolution=0.01, length=150).grid(row=row, column=2)

    for i, key in enumerate("abcd"):
        add_row(i, key, shared[f"{key}_expr"], shared[f"{key}_scale"])

    # Controls
    tk.Checkbutton(root, text="Pause animation", variable=shared["paused"]).grid(row=4, column=1, pady=5)
    tk.Checkbutton(root, text="Show grid", variable=shared["show_grid"]).grid(row=5, column=1)
    tk.Checkbutton(root, text="Show arrow", variable=shared["show_arrow"]).grid(row=6, column=1)
    tk.Button(root, text="Reset t", command=reset_t).grid(row=7, column=1, pady=8)

    # Launch renderer in background thread
    threading.Thread(target=render_loop, args=(shared,), daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    make_controls()
