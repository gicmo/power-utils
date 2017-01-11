project('ptdrain', ['c'],
        version: '1.0.0',
        meson_version: '>=0.31')

glib = dependency('glib-2.0', version: '>=2.32')
gio = dependency('gio-2.0', version: '>=2.32')

executable('ptdrain-record',
  'record.c',
  install: true,
  dependencies: [glib, gio]
)
