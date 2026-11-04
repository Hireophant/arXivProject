"""Read explicit lexical declarations for Khang's structural scanner.

No text substitution or TeX execution. Preamble declarations supply command
arity, theorem environment names, and exact math begin/end aliases. Dynamic
catcodes, conditionals and general delimited arguments remain unsupported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from .khang_lex import MATH_ENVS, group_end, line_end, scan

_CONTROL = re.compile(r'\\([A-Za-z@]+|[^A-Za-z@])')
_DEFINERS = frozenset(('newcommand','renewcommand','providecommand','DeclareRobustCommand',
                      'def','gdef','edef','xdef','let','DeclareMathOperator','newtheorem'))
_UNSAFE = re.compile(r'\\(?:input|include|if\w*|else|fi|catcode|csname|expandafter|'
                     r'newcommand|renewcommand|def|gdef|section|chapter|subsection|subsubsection|'
                     r'paragraph|subparagraph|part|begin|end|item|'
                     r'bibliography|bibitem)\b')
_INLINE = frozenset(('textbf','textit','textup','textsl','textsc','textsf','textrm','texttt',
    'emph','textnormal','text','underline','mbox','ensuremath','mathrm','mathbf','mathcal',
    'mathbb','mathsf','mathit','mathscr','boldsymbol','operatorname','left','right','middle',
    'frac','dfrac','tfrac','sqrt','hat','widehat','bar','overline','tilde','widetilde','vec',
    'dot','ddot','nabla','partial','ell','langle','rangle','lvert','rvert','lVert','rVert',
    'cdot','times','circ','prime','dagger','ast','sum','prod','int','max','min','sup','inf',
    'log','ln','exp','sin','cos','tan','lim','infty','alpha','beta','gamma','delta','epsilon',
    'varepsilon','zeta','eta','theta','vartheta','iota','kappa','lambda','mu','nu','xi',
    'pi','rho','varrho','sigma','tau','upsilon','phi','varphi','chi','psi','omega','Gamma',
    'Delta','Theta','Lambda','Xi','Pi','Sigma','Upsilon','Phi','Psi','Omega','leq','geq',
    'neq','sim','approx','equiv','in','notin','subset','subseteq','supset','cup','cap',
    'emptyset','to','mapsto','rightarrow','Rightarrow','quad','qquad','hspace','vspace',
    'ref','eqref','autoref','cref','Cref','cite','citep','citet','url','href','path',
    'textcolor','color','xspace','LaTeX','TeX','textsuperscript','textsubscript'))


@dataclass
class Declarations:
    arities: dict[str,int] = field(default_factory=dict)
    bodies: dict[str,str] = field(default_factory=dict)
    math_aliases: dict[str,tuple[str,str]] = field(default_factory=dict)
    heading_aliases: dict[str,str] = field(default_factory=dict)
    environments: set[str] = field(default_factory=set)
    ranges: list[tuple[int,int]] = field(default_factory=list)
    _inline_cache: dict[str,bool] = field(default_factory=dict,repr=False)

    def inline(self, name: str, seen: frozenset[str] = frozenset()) -> bool:
        """Prove no structural command is introduced by a declared macro."""
        if name in self._inline_cache:
            return self._inline_cache[name]
        if name in seen or name not in self.bodies or len(seen)>=32:
            return False
        self._inline_cache[name]=False
        body=self.bodies[name]
        if _UNSAFE.search(body) or any(t.kind in ('begin','end','block','break') for t in scan(body)):
            return False
        for command in _CONTROL.findall(body):
            if command in self.bodies and not self.inline(command,seen|{name}):
                return False
            if len(command)>1 and command not in self.bodies and command not in _INLINE:
                return False
        self._inline_cache[name]=True
        return True


def _space(text: str, offset: int) -> int:
    while offset<len(text):
        if text[offset].isspace():
            offset+=1
        elif text[offset]=='%':
            offset=line_end(text,offset)
        else:
            break
    return offset


def _group(text: str, offset: int) -> tuple[str,int]:
    offset=_space(text,offset)
    if offset>=len(text) or text[offset] not in '{[':
        raise ValueError('Expected declaration group')
    end,ok=group_end(text,offset,text[offset],'}' if text[offset]=='{' else ']')
    if not ok:
        raise ValueError('Unclosed declaration group')
    return text[offset+1:end-1],end


def declarations(text: str) -> Declarations:
    """Inspect active preamble declarations without opening any source files."""
    result=Declarations()
    covered=0
    conditional_depth=0
    for token in scan(text):
        if token.start<covered:
            continue
        if token.kind=='begin' and token.name=='document':
            break
        if token.kind=='command' and token.name=='newif':
            target=_CONTROL.match(text,_space(text,token.end))
            if target: covered=target.end()
            continue
        if token.kind=='command' and token.name.startswith('if'):
            conditional_depth+=1
            continue
        if token.kind=='command' and token.name=='fi' and conditional_depth:
            conditional_depth-=1
            continue
        if conditional_depth:
            continue
        if token.kind not in ('command','declaration') or token.name not in _DEFINERS:
            continue
        match=_CONTROL.match(text,token.start)
        cursor=match.end()
        if cursor<len(text) and text[cursor]=='*': cursor+=1
        try:
            if token.name=='newtheorem':
                name,end=_group(text,cursor)
                result.environments.add(name.strip())
                continue
            if token.name in ('def','gdef','edef','xdef','let'):
                target=_CONTROL.match(text,_space(text,cursor))
                if target is None: continue
                name=target[1]; cursor=target.end()
                result.math_aliases.pop(name,None)
                if token.name=='let':
                    cursor=_space(text,cursor)
                    if cursor<len(text) and text[cursor]=='=': cursor+=1
                    alias=_CONTROL.match(text,_space(text,cursor))
                    if alias:
                        result.bodies[name]='\\'+alias[1]
                        result.arities[name]=result.arities.get(alias[1],0)
                        result.ranges.append((token.start,alias.end()))
                        covered=alias.end()
                    continue
                opening=text.find('{',cursor)
                if opening<0: continue
                parameters=text[cursor:opening].strip()
                body,end=_group(text,opening)
                # Common delimited display macro: \def\al#1\eal{\begin{align}#1\end{align}}.
                parameter=re.fullmatch(r'#1\s*\\([A-Za-z@]+)',parameters)
                environment=re.fullmatch(r'\s*\\begin\{([^}]+)\}\s*#1\s*\\end\{\1\}\s*',body)
                if parameter and environment and environment[1] in MATH_ENVS:
                    result.math_aliases[name]=('begin',environment[1])
                    result.math_aliases[parameter[1]]=('end',environment[1])
                    result.arities[name]=0
                    # The delimiter terminates #1; it takes no following group.
                    # Otherwise scan() can swallow grouped prose after the math.
                    result.arities[parameter[1]]=0
                elif not parameters or re.fullmatch(r'(?:#[1-9])+',parameters):
                    result.arities[name]=len(parameters)//2
                    result.bodies[name]=body
                else:
                    continue
            else:
                cursor=_space(text,cursor)
                if cursor<len(text) and text[cursor]=='{':
                    target,cursor=_group(text,cursor)
                    command=_CONTROL.fullmatch(target.strip())
                else:
                    command=_CONTROL.match(text,cursor)
                    if command: cursor=command.end()
                if command is None: continue
                name=command[1];arity=0
                result.math_aliases.pop(name,None)
                cursor=_space(text,cursor)
                if cursor<len(text) and text[cursor]=='[':
                    count,cursor=_group(text,cursor)
                    if not count.isdigit() or not 0<=int(count)<=9: continue
                    arity=int(count)
                    cursor=_space(text,cursor)
                    if cursor<len(text) and text[cursor]=='[':
                        # Optional defaults are kept opaque; do not infer call arity.
                        continue
                body,end=_group(text,cursor)
                result.bodies[name]=body;result.arities[name]=arity
            result.ranges.append((token.start,end));covered=end
        except ValueError:
            continue
    for name,body in result.bodies.items():
        heading=re.search(r'\\(chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\s*\{#1\}',body)
        if result.arities.get(name)==1 and heading and all(
                t.kind=='comment' or (t.kind=='text' and not body[t.start:t.end].strip()) or
                (t.kind=='command' and t.name in (heading[1],'addcontentsline','protect','relax','noindent','phantomsection'))
                for t in scan(body)):
            result.heading_aliases[name]=heading[1]
        alias=re.fullmatch(r'\s*\\(begin|end)\{([^}]+)\}\s*',body)
        if alias and alias[2] in MATH_ENVS:
            result.math_aliases[name]=(alias[1],alias[2])
        else:
            body_tokens=list(scan(body))
            envs=[t for t in body_tokens if t.kind in ('begin','end')]
            if len(envs)==1 and envs[0].name in MATH_ENVS and all(
                t is envs[0] or t.kind=='comment' or
                (t.kind=='text' and not body[t.start:t.end].strip()) or
                (t.kind=='command' and t.name in ('label','nonumber','notag'))
                for t in body_tokens):
                result.math_aliases[name]=(envs[0].kind,envs[0].name)
    # Resolve simple alias chains, without expanding text or guessing unknown commands.
    for _ in range(16):
        changed=False
        for name,body in result.bodies.items():
            target=_CONTROL.fullmatch(body.strip())
            if name not in result.math_aliases and target and target[1] in result.math_aliases:
                result.math_aliases[name]=result.math_aliases[target[1]];changed=True
        if not changed: break
    return result
