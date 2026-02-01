package fonts

import (
	"bytes"
	"embed"
	"io"
)

//go:embed double_blocky.flf
var fs embed.FS

// LoadFont returns a reader for the named font file (e.g. "double_blocky").
func LoadFont(name string) io.Reader {
	data, err := fs.ReadFile(name + ".flf")
	if err != nil {
		return nil
	}
	return bytes.NewReader(data)
}
