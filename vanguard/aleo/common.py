import argparse
import subprocess
import logging
import inspect
import shlex
import shutil
import json
import os

from pathlib import Path
from typing import List, Union

# ref (Aleo grammar): https://developer.aleo.org/aleo/grammar/

def run_command(cmd: Union[str, List[Union[str, Path]]], decode=True):
    if isinstance(cmd, str):
        logging.info(f"  cmd: {cmd}")
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    elif isinstance(cmd, list):
        logging.info(f"  cmd: {shlex.join(map(str, cmd))}")
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        raise Exception(f"unsupported command type, got: {cmd}")
    
    if proc.returncode != 0:
        err_contents = proc.stdout.decode("utf-8")
        raise Exception(f"command failed with message:\n{err_contents}")
    
    return proc.stdout.decode() if decode else proc.stdout

def aleo2json(path: Union[str, Path]):
    cmd = ["aleo2json", path]
    out = run_command(cmd)
    return json.loads(out)

def assert_node_field(node, field, val=None):
    assert field in node.keys(), f"Can't find filed {field} in node"
    if val is not None:
        assert node[field] == val, f"Mismatch of {field} of node, expected: {val}, got: {node[field]}"

def assert_range(value, range):
    assert value in range, f"Value {value} is not in range {range}"

def get_ifg_edges(prog, func, hash=False, call=False, inline=False):
    """Get information flow graph edges.
    Args:
      - prog: 
      - func
      - hash (default: False): whether to treat a hash function call directly as an edge
      - call (default: False): whether to treat a call directly as an edge
      - inline (default: False): whether to inline call invocations recursively to generate edges;
        if `call` is True, this argument is then overridden and no inlining will take place.
    Rets: A list of pairs of strings
    """
    node = prog.functions[func]
    assert_node_field(node, "instructions")

    edges = []
    # process instructions
    for inst in node["instructions"] + node["outputs"]:
        tokens = inst["str"].strip(";").split()
        match tokens:

            case ["is.eq", o1, o2, "into", r]:
                edges.append((o1, r))
                edges.append((o2, r))
            case ["is.neq", o1, o2, "into", r]:
                edges.append((o1, r))
                edges.append((o2, r))
            
            case ["assert.eq", o1, o2]:
                edges.append((o1, o2))
                edges.append((o2, o1))
            case ["assert.neq", o1, o2]:
                edges.append((o1, o2))
                edges.append((o2, o1))

            case ["cast", o, "into", r, "as", d]:
                edges.append((o, r))

            case ["call", f, *os, "into", r]:
                if call:
                    for o in os:
                        edges.append((o, r))
                elif inline:
                    # TODO: add impl
                    raise NotImplementedError
                else:
                    # no inline, no call, then no edge
                    pass

            case [cop, o1, o2, "into", r, "as", t] if cop.startswith("commit"):
                # no edge in commitment computation
                pass

            case [hop, o1, "into", r, "as", t] if hop.startswith("hash"):
                # no edge in hash computation
                pass

            case [binop, o1, o2, "into", r]:
                edges.append((o1, r))
                edges.append((o2, r))
            
            case [unop, o, "into", r]:
                edges.append((o, r))
            
            case [terop, o1, o2, o3, "into", r]:
                edges.append((o1, r))
                edges.append((o2, r))
                edges.append((o3, r))

            case ["cast", *os, "into", dst, "as", typ]:
                for o in os:
                    edges.append((o, dst))
            
            case _:
                raise NotImplementedError(f"Unknown instruction pattern, got: {inst['str']}")

    return edges

def get_dfg_edges(prog, func):
    """Get data flow graph edges.
    Args:
      - prog: 
      - func:
    Rets: A list of pairs of strings
    """
    node = prog.functions[func]
    assert_node_field(node, "instructions")

    edges = []
    # process instructions
    for inst in node["instructions"]:
        tokens = inst["str"].strip(";").split()
        match tokens:

            case ["is.eq", o1, o2, "into", r]:
                edges.append((o1, r))
                edges.append((o2, r))
            case ["is.neq", o1, o2, "into", r]:
                edges.append((o1, r))
                edges.append((o2, r))
            
            case ["assert.eq", o1, o2]:
                edges.append((o1, o2))
                edges.append((o2, o1))
            case ["assert.neq", o1, o2]:
                edges.append((o1, o2))
                edges.append((o2, o1))

            case ["cast", o, "into", r, "as", d]:
                edges.append((o, r))

            case ["call", f, *os, "into", r]:
                # no inlining, just add edge from this level
                for o in os:
                    edges.append((o, r))

            case [cop, o1, o2, "into", r, "as", t] if cop.startswith("commit"):
                edges.append((o1, r))
                edges.append((o2, r))

            case [hop, o1, "into", r, "as", t] if hop.startswith("hash"):
                edges.append((o1, r))

            case [binop, o1, o2, "into", r]:
                edges.append((o1, r))
                edges.append((o2, r))
            
            case [unop, o, "into", r]:
                edges.append((o, r))
            
            case [terop, o1, o2, o3, "into", r]:
                edges.append((o1, r))
                edges.append((o2, r))
                edges.append((o3, r))

            case ["cast", *os, "into", dst, "as", typ]:
                for o in os:
                    edges.append((o, dst))
            
            case _:
                raise NotImplementedError(f"Unknown instruction pattern, got: {inst['str']}")

    return edges