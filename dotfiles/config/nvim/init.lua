-- Define the path where lazy.nvim will be installed
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
-- Check if lazy.nvim is not already installed
if not vim.loop.fs_stat(lazypath) then
  -- Clone the stable branch of lazy.nvim from GitHub into the defined path
  vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",  -- Only clone the necessary parts
    "https://github.com/folke/lazy.nvim.git",  -- Repository URL
    "--branch=stable",  -- Specify the stable branch
    lazypath,
  })
end
-- Prepend the lazy.nvim plugin to runtime path (rtp) for Vim to recognize it
vim.opt.rtp:prepend(lazypath)

-- Load the options module
require("options")

-- Load the plugins module
require("lazy").setup("plugins")
