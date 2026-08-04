return {
	{
    	'nvim-telescope/telescope.nvim', tag = '0.1.8',  -- Specify a specific version tag for Telescope
    	dependencies = { 'nvim-lua/plenary.nvim' },  -- Telescope depends on the plenary.nvim library
    	config = function()
    	    -- Load telescope's built-in functions
    	    local builtin = require("telescope.builtin")
    	    -- Map Ctrl+p to Telescope's find_files function in normal mode
    	    vim.keymap.set('n', '<C-p>', builtin.find_files, {})
    	    -- Map Ctrl+o to Telescope's livegrep
    	    vim.keymap.set('n', '<C-o>', builtin.live_grep, { desc = 'Telescope live grep' })
    	end
	},
	{
		"nvim-telescope/telescope-ui-select.nvim",
		config = function()
			require("telescope").setup({
  				extensions = {
    				["ui-select"] = {
      					require("telescope.themes").get_dropdown {
      					}
    				}
  				}
			})
			require("telescope").load_extension("ui-select")
		end
	}
}
