;;; files.el --- Measure visible file opening and exercise editing -*- lexical-binding: t; -*-
(require 'json)
(defun benchmark-files (files &optional exercise)
  (vconcat
   (mapcar
    (lambda (file)
      (let ((start (float-time)))
        (find-file file)
        (when (and exercise (equal (getenv "TRAIN_BALANCED_GAP") "1"))
          ;; A neutral editing position lets scans encounter both sides of the gap.
          (save-excursion
            (goto-char (/ (+ (point-min) (point-max)) 2))
            (insert " ")
            (delete-char -1))
          (set-buffer-modified-p nil))
        (redisplay t)
        (when font-lock-mode
          (font-lock-ensure (window-start) (window-end nil t)))
        (redisplay t)
        (let ((elapsed (- (float-time) start)))
          (when exercise
            (dotimes (_ 5)
              (goto-char (point-min))
              (search-forward "benchmark" nil t)
              (forward-line 30)
              (insert "temporary benchmark text\n")
              (delete-region (line-beginning-position 0) (line-beginning-position))
              (goto-char (/ (+ (point-min) (point-max)) 2))
              (recenter)
              (ignore-errors (scroll-up 10))
              (all-completions "find-" obarray #'commandp)
              (file-name-all-completions "" default-directory)
              (redisplay t))
            (set-buffer-modified-p nil))
          (let ((mode (symbol-name major-mode)))
            (kill-buffer)
            `((file . ,(file-name-nondirectory file)) (mode . ,mode)
              (open_seconds . ,elapsed))))))
    files)))
