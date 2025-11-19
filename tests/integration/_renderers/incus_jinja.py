'''
Custom Jinja renderer that overrides tpldir for formula testing.
'''

import salt.renderers.jinja as jinja


def render(template, saltenv='base', sls='', **kws):
    '''
    Wrapper around Salt's built-in Jinja renderer.
    Allows overriding tpldir to match production layout.
    '''

    # Вызов оригинального рендерера Jinja:
    out = jinja.render(template, saltenv, sls, **kws)

    # context доступен в kws: __context__
    ctx = kws.get("__context__", {})

    # если Salt загрузил tpldir — подменяем
    tpldir = ctx.get("tpldir")

    ctx["tpldir"] = "."


    return out
