return {
    "nvim-neo-tree/neo-tree.nvim",
    branch = "v3.x",
    dependencies = {
        "nvim-lua/plenary.nvim",
        "nvim-tree/nvim-web-devicons",
        "MunifTanjim/nui.nvim",
    },
    config = function()
        -- Correct the require statement
        require("neo-tree").setup({
            filesystem = {
                filtered_items = {
                    hide_dotfiles = false,  -- Show hidden files (those starting with a dot)
                    hide_gitignored = false, -- (Optional) Show files ignored by Git
                }
            }
        })
        -- Set keymap to toggle Neo-tree on <C-n>
        vim.keymap.set('n', '<C-n>', ':Neotree filesystem toggle left<CR>')
    end
}
