-- Set tab width to 4 spaces
vim.cmd("set tabstop=4")
-- Set indentation width to 4 spaces
vim.cmd("set shiftwidth=4")
-- Use actual tab characters instead of spaces
vim.cmd("set noexpandtab")

vim.g.mapleader = " "

vim.api.nvim_set_keymap('n', '<leader>w', ':w<CR>', { noremap = true, silent = true })  -- Save file
vim.api.nvim_set_keymap('n', '<leader>q', ':q<CR>', { noremap = true, silent = true })  -- Quit Neovim
