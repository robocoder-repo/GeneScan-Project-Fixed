<?php

$file = 'data/bands/ncbi/ideogram_banana_v0.1.tsv';
$maxSvgLength = 10000;


$handle = fopen ( $file, 'rb' );


$fields = fgetcsv($handle, 0, "\t");
$bands = array ();


for ($i = 0; ($row = fgetcsv($handle, 0, "\t")) !== false; $i ++) {
    foreach ($row as $k => $value) {
        $bands[$i][$fields[$k]] = $value == 'na' ? null : $value;
    }
}


$maxChrLength = max(array_column($bands, 'bp_stop'));


echo 'chrBands = [', "\n";
foreach ($bands as $band) {
    if ($band['arm'] == 'p') {
        echo '    "' . $band['#chromosome'] . ' ' . $band['arm'] . ' 1 0 ' . round($band['bp_stop'] / $maxChrLength * $maxSvgLength) . '",',
             "\n";
    } else {
        echo '    "' . $band['#chromosome'] . ' ' . $band['arm'] . ' 1 0 ' . round($band['bp_stop'] / $maxChrLength * $maxSvgLength) . '",',
             "\n";
    }
}
echo '];', "\n";