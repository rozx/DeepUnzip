# DeepUnzip demo GIF (Chinese). See docs/demo.tape for how to run it.
#   vhs docs/demo.zh.tape     # writes docs/images/demo-zh.gif

Output docs/images/demo-zh.gif

Set Shell "bash"
Set FontSize 16
Set Width 1000
Set Height 600
Set Padding 16
Set TypingSpeed 40ms
Set Theme "Dracula"

Hide
Type "export DEEPUNZIP_LANG=zh PS1='$ '" Enter
Type `alias deepunzip="$(poetry env info -p)/bin/deepunzip"` Enter
Type "rm -rf /tmp/deepunzip-demo && poetry run python -m scripts.make_demo_archives /tmp/deepunzip-demo --concert-mb 400 > /dev/null" Enter
Sleep 8s
Type "cd /tmp/deepunzip-demo && clear" Enter
Sleep 500ms
Show

Type "ls" Enter
Sleep 1500ms
Type "deepunzip --permanent-delete ." Enter
Sleep 8s
Type "ls unzipped" Enter
Sleep 3s
