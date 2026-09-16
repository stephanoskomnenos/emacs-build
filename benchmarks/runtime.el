;;; runtime.el --- Run the locked upstream Elisp benchmarks -*- lexical-binding: t; -*-
(require 'json)
(load (expand-file-name "elisp-benchmarks.el" (getenv "BENCHMARK_SUITE")) nil t)
(advice-add 'elb--display :override
            (lambda (tests results runs)
              (let ((rows (mapcar
                           (lambda (name)
                             (let ((samples (gethash name results)))
                               (unless (= (length samples) runs)
                                 (error "Missing benchmark result: %s" name))
                               `((name . ,name) (seconds . ,(vconcat (mapcar #'car samples))))))
                           tests)))
                (with-temp-file (getenv "BENCHMARK_RESULT")
                  (insert (json-serialize `((runs . ,runs) (results . ,(vconcat rows)))))))))
(elisp-benchmarks-run (getenv "BENCHMARK_SELECTOR") t
                      (string-to-number (or (getenv "BENCHMARK_RUNS") "3")))
