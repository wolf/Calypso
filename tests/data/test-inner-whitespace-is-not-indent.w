<<generated_output>>=
(define (fizz-buzz limit)
  (for ([i (in-range 1 (add1 limit))])
    (let <<B>>
      (when is-multiple-of-3
        (write 'Fizz))
      (when <<D>>)
      (unless (or is-multiple-of-3 is-multiple-of-5)
        (write i))
      <<C>>)))
<<B>>=
([is-multiple-of-3 (zero? (modulo i 3))]
          [is-multiple-of-5 (zero? (modulo i 5))])
<<C>>=
(newline)
<<D>>=
is-multiple-of-5
        (write 'Buzz)
