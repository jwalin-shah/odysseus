tell application "System Events"
    tell process "Antigravity"
        set p to position of window 1
        set s to size of window 1
        return (item 1 of p) & "," & (item 2 of p) & "," & (item 1 of s) & "," & (item 2 of s)
    end tell
end tell
