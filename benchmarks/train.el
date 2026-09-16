;;; train.el --- Generic training; never loads the user's configuration -*- lexical-binding: t; -*-
(load (expand-file-name "files.el" (file-name-directory load-file-name)) nil t)
(setq inhibit-startup-screen t
      make-backup-files nil
      auto-save-default nil)
(add-hook 'window-setup-hook
          (lambda ()
            (run-at-time
             0 nil
             (lambda ()
               (condition-case err
                   (progn
                     (require 'org)
                     (require 'cc-mode)
                     (let ((files (directory-files (getenv "PGO_CORPUS") t "\\.\\(c\\|el\\|org\\|txt\\)\\'")))
                       (unless files (error "Training corpus is empty"))
                       (dotimes (_ 3) (benchmark-files files t)))
                     (kill-emacs 0))
                 (error (message "PGO training failed: %S" err) (kill-emacs 1)))))) t)
