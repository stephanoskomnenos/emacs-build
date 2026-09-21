;;; gui.el --- NS training and held-out GUI measurements -*- lexical-binding: t; -*-
(require 'json)
(defconst eb-gui-directory (file-name-directory load-file-name))
(defvar eb-results nil)

(defun eb-record (name start)
  (push (cons name (* 1000.0 (- (float-time) start))) eb-results))

(defun eb-write (name data)
  (with-temp-file (expand-file-name name (getenv "GUI_OUTPUT"))
    (insert (json-encode data))))

(defun eb-operation (name function)
  (let ((start (float-time)))
    (funcall function)
    (redisplay t)
    (eb-record name start)))

(defun eb-average-operation (name count function)
  "Repeat one original workload unit COUNT times and record average milliseconds."
  (let ((start (float-time)))
    (dotimes (_ count)
      (funcall function)
      (redisplay t))
    (push (cons name (/ (* 1000.0 (- (float-time) start)) count))
          eb-results)))

(defun eb-open-file-once (name corpus)
  (let* ((path (expand-file-name name corpus))
         (buffer (find-file-noselect path)))
    (switch-to-buffer buffer)
    (font-lock-ensure)
    (goto-char (point-min))
    (redisplay t)
    (set-buffer-modified-p nil)
    (kill-buffer buffer)))

(defun eb-compare-workloads (corpus)
  ;; Preserve fresh-process first-open cost, then measure repeated opens
  ;; separately so short file workloads have a lower-noise steady signal.
  (dolist (spec '(("held-out.el-first" . "held-out.el")
                  ("held-out.org-first" . "held-out.org")
                  ("held-out.txt-first" . "held-out.txt")))
    (eb-average-operation (car spec) 1
                          (lambda () (eb-open-file-once (cdr spec) corpus))))
  (dolist (spec '(("held-out.el-steady" 8 "held-out.el")
                  ("held-out.org-steady" 2 "held-out.org")
                  ("held-out.txt-steady" 64 "held-out.txt")))
    (eb-average-operation (nth 0 spec) (nth 1 spec)
                          (lambda () (eb-open-file-once (nth 2 spec) corpus))))

  ;; Leave a held-out text buffer active for the interactive and CPU workloads.
  (find-file (expand-file-name "held-out.txt" corpus))
  (font-lock-ensure)
  (goto-char (point-min))

  ;; Each repetition below is one copy of the previous compare workload.
  ;; Amplification amortizes hosted-runner scheduler noise without changing
  ;; the reported unit.
  (eb-average-operation
   "scroll-edit" 8
   (lambda ()
     (dotimes (_ 30)
       (goto-char (point-min))
       (forward-line 20)
       ;; Keyboard macros exercise commands, not OS keyboard injection.
       (execute-kbd-macro "xyz")
       (delete-char -3)
       (recenter) (redisplay t)
       (scroll-up 5) (redisplay t))))
  (eb-average-operation
   "window-layout" 12
   (lambda ()
     (dotimes (_ 10)
       (split-window-right) (redisplay t) (delete-other-windows)
       (text-scale-increase 1) (redisplay t) (text-scale-decrease 1))))
  (eb-average-operation
   "regexp" 1
   (lambda ()
     (dotimes (_ 100)
       (goto-char (point-min))
       (while (re-search-forward "[[:alpha:]]+[-_]?[0-9]+" nil t)))))
  (eb-average-operation
   "json" 10
   (lambda ()
     (let ((text (json-encode (vconcat (number-sequence 0 2000)))))
       (dotimes (_ 120)
         (json-parse-string text))))))

(defun eb-run ()
  (condition-case err
      (progn
        (unless (and (eq window-system 'ns)
                     (display-graphic-p)
                     (eq (frame-visible-p (selected-frame)) t))
          (error "A visible Cocoa frame is required"))
        (redisplay t)
        (eb-write "ready.json"
                  `((time . ,(float-time)) (window_system . ,window-system)))
        (when (equal (getenv "GUI_MODE") "smoke")
          (when (and (fboundp 'native-comp-available-p)
                     (native-comp-available-p))
            (error "Native compilation must be disabled"))
          (dolist (feature '("NS" "GNUTLS" "LIBXML2" "TREE_SITTER"
                             "ZLIB" "MODULES" "KQUEUE" "SQLITE3"))
            (unless (member feature (split-string system-configuration-features))
              (error "Missing required build feature: %s" feature)))
          (unless (and (gnutls-available-p)
                       (libxml-available-p)
                       (treesit-available-p))
            (error "A configured library is unavailable at runtime"))
          (require 'sqlite)
          (unless (sqlite-available-p)
            (error "SQLite unavailable"))
          (let ((db (sqlite-open)))
            (unwind-protect
                (progn
                  (sqlite-execute db "create table smoke (v text)")
                  (sqlite-execute db "insert into smoke values (?)" '("中文"))
                  (unless (equal (sqlite-select db "select v from smoke")
                                 '(("中文")))
                    (error "SQLite roundtrip failed")))
              (sqlite-close db)))
          (dolist (path (list data-directory exec-directory
                              (locate-library "org")))
            (unless (and path
                         (file-in-directory-p
                          (file-truename path)
                          (file-truename (getenv "GUI_APP"))))
              (error "Resource outside app bundle: %S" path))))
        (let* ((training (equal (getenv "GUI_MODE") "train"))
               (comparing (equal (getenv "GUI_MODE") "compare"))
               (corpus (getenv "GUI_CORPUS")))
          (cond
           (comparing
            (eb-compare-workloads corpus))
           (t
            ;; Preserve the existing training and smoke workload semantics.
            (dolist (name (if training
                              '("buffer.c" "files.el" "org-news.org" "news.txt")
                            '("held-out.el" "held-out.org" "held-out.txt")))
              (eb-operation
               name
               (lambda ()
                 (find-file (expand-file-name name corpus))
                 (font-lock-ensure)
                 (goto-char (point-min)))))
            (eb-operation
             "scroll-edit"
             (lambda ()
               (dotimes (_ (if training 60 1))
                 (goto-char (point-min))
                 (forward-line 20)
                 (execute-kbd-macro "xyz")
                 (delete-char -3)
                 (recenter) (redisplay t)
                 (scroll-up 5) (redisplay t))))
            (eb-operation
             "window-layout"
             (lambda ()
               (dotimes (_ (if training 10 1))
                 (split-window-right) (redisplay t) (delete-other-windows)
                 (text-scale-increase 1) (redisplay t)
                 (text-scale-decrease 1))))
            (when training
              (load (expand-file-name "training.el" eb-gui-directory) nil t)
              (eb-train-interactions))))
          (eb-write "result.json" eb-results))
        (set-buffer-modified-p nil)
        (kill-emacs 0))
    (error
     (eb-write "error.json" (format "%S" err))
     (kill-emacs 1))))

(add-hook 'emacs-startup-hook (lambda () (run-at-time 0 nil #'eb-run)))
