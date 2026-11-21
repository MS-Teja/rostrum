"""Small helpers for building shader node trees in code. GPL-3.0-or-later.

    from cine.blender import nodes
    m, N, L = nodes.fresh("die")              # a material with an empty node tree
    op = nodes.maths(N, L)                    # op("MULTIPLY", socket_or_number, socket_or_number, clamp=False)
    t = nodes.time_value(m.node_tree, fps)    # a Value node reading the scene time in seconds
    nodes.add_shader(N, L, a, b)              # two shader nodes added
"""

import bpy


def fresh(name):
    """A new material with nodes on and its default nodes removed: (material, nodes, links)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return m, nt.nodes, nt.links


def maths(N, L):
    """A Math-node maker: op(kind, a, b=None, clamp=False), each input a socket or a number.
    Returns the node's output socket."""
    def op(kind, a, b=None, clamp=False):
        n = N.new("ShaderNodeMath")
        n.operation = kind
        n.use_clamp = clamp
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]
    return op


def time_value(nt, fps):
    """A Value node that reads the scene time in seconds (a driver on the frame)."""
    v = nt.nodes.new("ShaderNodeValue")
    fc = v.outputs[0].driver_add("default_value")
    fc.driver.expression = f"frame / {fps}"
    return v


def add_shader(N, L, a, b):
    add = N.new("ShaderNodeAddShader")
    L.new(a.outputs[0], add.inputs[0])
    L.new(b.outputs[0], add.inputs[1])
    return add
