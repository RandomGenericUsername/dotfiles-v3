@import url("{{COLORS_FILE_PATH}}");

* {
    font-family: {{SYSTEM_FONT_FAMILY}};
	transition: 20ms;
	box-shadow: none;
	font-size: {{FONT_SIZE_PX}}px; /* Only supports px */
    background-image: none;
	background: none;
}

window {
    background-image: none;
	background: url("{{CURRENT_WALLPAPER_SYMLINK}}");
	background-size: cover;
    font-size: 1em;
}

button {
    color: @color_15;
    border-radius: 1em;
	border: 0em;
    padding: 0.5em;
    background-repeat: no-repeat;
    background-position: center;
    background-color: transparent;
    background-size: 20%;
    animation: gradient_f 20s ease-in infinite;
	transition: all 0.3s cubic-bezier(.55, 0.0, .28, 1.682), box-shadow 0.2s ease-in-out, background-color 0.2s ease-in-out;
    -gtk-icon-effect: none;
}

button:focus, button:hover {
    background-color: @color_12;
	opacity: 0.8;
    background-size: 30%;
    box-shadow: 0 0 0.9em @color_07;
}

button span {
    font-size: 1.2em;
}

#lock {
    background-image: image(url("{{STATE_ROOT}}/dotfiles/current/icons/lock.svg"));
}

#logout {
    background-image: image(url("{{STATE_ROOT}}/dotfiles/current/icons/logout.svg"));
}

#suspend {
    background-image: image(url("{{STATE_ROOT}}/dotfiles/current/icons/suspend.svg"));
}

#hibernate {
    background-image: image(url("{{STATE_ROOT}}/dotfiles/current/icons/hibernate.svg"));
}

#shutdown {
    background-image: image(url("{{STATE_ROOT}}/dotfiles/current/icons/shutdown.svg"));
}

#reboot {
    background-image: image(url("{{STATE_ROOT}}/dotfiles/current/icons/reboot.svg"));
}
