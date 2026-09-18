;;; training.el --- Additional Cocoa training using shared fixtures -*- lexical-binding: t; -*-

;; Reuse the terminal workload's packages, JSON filter and process producer.
;; Loaded after GUI startup, so its terminal window-setup hook is not run.
(load (expand-file-name "../interactive/training.el"
                        (file-name-directory load-file-name)) nil t)

(defun eb-train-wait (pending)
  (let ((deadline (+ (float-time) 30)))
    (while (funcall pending)
      (when (> (float-time) deadline) (error "GUI training process timed out"))
      (accept-process-output nil 0.01)
      (redisplay t))))

(defun eb-train-interactions ()
  (let ((fixtures (getenv "TRAIN_FIXTURES")))
    (eb-operation
     "search-completion"
     (lambda ()
       (find-file (expand-file-name "mixed-lines.txt" fixtures))
       (dotimes (_ 4)
         (goto-char (point-min))
         (while (re-search-forward "training needle\\|ordinary entry" nil t))
         (goto-char (point-min))
         (search-forward "needle")
         (recenter) (redisplay t))
       ;; Candidate generation only; real minibuffer input is covered by PTY.
       (unless (and (all-completions "find-f" obarray #'commandp)
                    (file-name-all-completions
                     "common-fi" (expand-file-name "completion/project alpha/src/" fixtures)))
         (error "GUI completion training produced no candidates"))))
    (eb-operation
     "org-structure"
     (lambda ()
       (require 'org)
       (find-file (expand-file-name "notebook.org" fixtures))
       (org-overview) (redisplay t)
       (org-show-all) (redisplay t)
       (goto-char (point-min)) (search-forward "alpha")
       (org-table-align)
       (org-table-next-field)
       (goto-char (point-min)) (search-forward "Deep detail")
       (beginning-of-line) (org-cycle) (redisplay t)))
    (eb-operation
     "process-json"
     (lambda ()
       (dolist (variant '("fragmented" "batched"))
         (setenv "TRAIN_PROCESS_VARIANT" variant)
         (train-process)
         (eb-train-wait (lambda () (not train-finished)))
         (unless (and (null train-error) (= train-lines 180)
                      (= train-value (/ (* 180 179) 2))
                      (= (hash-table-count train-documents) 9))
           (error "GUI JSON training failed: %S" train-error)))
       (let ((compilation-save-buffers-predicate #'ignore))
         (compile (concat "python3 " (shell-quote-argument (getenv "TRAIN_PRODUCER"))
                          " compile")))
       (eb-train-wait (lambda () compilation-in-progress))
       (unless (equal train-compilation-status "finished")
         (error "GUI compilation training failed: %s" train-compilation-status))))
    (eb-operation
     "magit-display"
     (lambda ()
       (require 'magit)
       (let ((default-directory (file-name-as-directory
                                 (expand-file-name "repository-small" fixtures))))
         (magit-status default-directory) (redisplay t)
         (magit-diff-unstaged) (redisplay t)
         (magit-status default-directory)
         (magit-log-current) (redisplay t)
         (unless (with-current-buffer (window-buffer (selected-window))
                   (derived-mode-p 'magit-log-mode))
           (error "GUI Magit history did not open")))))))
