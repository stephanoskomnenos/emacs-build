;;; smoke.el --- Portable package acceptance tests -*- lexical-binding: t; -*-
(require 'ert)
(require 'gnutls)
(require 'sqlite)
(require 'treesit)
(require 'xml)
(require 'filenotify)

(ert-deftest portable-features ()
  (should (gnutls-available-p))
  (should-not (string-match-p "NATIVE_COMP" system-configuration-features))
  (should-not (and (fboundp 'native-comp-available-p) (native-comp-available-p)))
  (dolist (feature '("GNUTLS" "GMP" "LIBXML2" "SQLITE3" "TREE_SITTER"
                     "MODULES" "THREADS" "INOTIFY" "ZLIB"))
    (should (member feature (split-string system-configuration-features))))
  (should-not (display-graphic-p)))

(ert-deftest portable-runtime-data ()
  (should (file-directory-p data-directory))
  (should (file-directory-p doc-directory))
  (should (documentation 'car))
  (should (locate-library "org"))
  (should (require 'org))
  (should (equal (decode-coding-string (encode-coding-string "中文测试" 'utf-8) 'utf-8)
                 "中文测试")))

(ert-deftest portable-sqlite ()
  (should (sqlite-available-p))
  (let ((db (sqlite-open)))
    (unwind-protect
        (progn (sqlite-execute db "create table t (v text)")
               (sqlite-execute db "insert into t values (?)" '("中文"))
               (should (equal (sqlite-select db "select v from t") '(("中文")))))
      (sqlite-close db))))

(ert-deftest portable-xml ()
  (with-temp-buffer
    (insert "<root><text>hello</text></root>")
    (should (eq (car (libxml-parse-xml-region (point-min) (point-max))) 'root))))

(ert-deftest portable-subprocess ()
  (with-temp-buffer
    (should (= 0 (call-process "/bin/sh" nil t nil "-c" "printf subprocess-ok")))
    (should (equal (buffer-string) "subprocess-ok"))))

(ert-deftest portable-external-module ()
  (let ((module (getenv "TEST_MODULE")))
    (should module)
    (module-load module)
    (should (= (portable-module-answer) 42))))

(ert-deftest portable-vterm ()
  (let ((load-path (cons (getenv "TEST_VTERM") load-path)))
    (require 'vterm)
    (let ((vterm-shell "/bin/sh")
          (vterm-always-compile-module nil)
          (kill-buffer-query-functions nil))
      (with-temp-buffer
        (vterm-mode)
        (should vterm--term)
        (vterm--write-input vterm--term "portable-vterm-ok\r\n")
        (let ((inhibit-read-only t)) (vterm--redraw vterm--term))
        (goto-char (point-min))
        (should (search-forward "portable-vterm-ok" nil t))))))

(ert-deftest portable-inotify ()
  (let* ((dir (make-temp-file "portable-notify-" t))
         (watch (file-notify-add-watch dir '(change) #'ignore)))
    (unwind-protect (should (file-notify-valid-p watch))
      (file-notify-rm-watch watch)
      (delete-directory dir))))

(ert-deftest portable-tree-sitter-engine ()
  (should (treesit-available-p))
  (let ((treesit-extra-load-path (list (getenv "TEST_GRAMMARS"))))
    (should (treesit-language-available-p 'json))
    (with-temp-buffer
      (insert "{\"hello\": [1, 2, 3]}")
      (let* ((parser (treesit-parser-create 'json))
             (root (treesit-parser-root-node parser)))
        (should (equal (treesit-node-type root) "document"))
        (should-not (treesit-node-check root 'has-error))))))

(ert-run-tests-batch-and-exit)
